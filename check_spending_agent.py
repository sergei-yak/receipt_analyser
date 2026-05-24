import os
import base64
import hashlib
import uuid
import pandas as pd
import matplotlib.pyplot as plt

from typing import Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI


load_dotenv()

BASE_DATA_FOLDER = "user_data"
PLOTS_FOLDER = "plots"

os.makedirs(BASE_DATA_FOLDER, exist_ok=True)
os.makedirs(PLOTS_FOLDER, exist_ok=True)


class CheckRecord(BaseModel):
    date: Optional[str] = Field(description="Transaction date in YYYY-MM-DD format")
    merchant: Optional[str] = Field(description="Store, company, or payee name")
    amount: Optional[float] = Field(description="Total amount paid")
    category: Optional[str] = Field(description="Spending category")
    memo: Optional[str] = Field(description="Short description")


class PlotPlan(BaseModel):
    chart_type: Literal["bar", "line", "pie", "histogram"]
    x_column: Optional[Literal["date", "merchant", "category"]] = None
    y_column: Literal["amount"] = "amount"
    group_by: Optional[Literal["date", "merchant", "category"]] = None
    aggregation: Literal["none", "sum", "count", "average", "cumulative_sum"]
    title: str


class AgentState(BaseModel):
    user_message: str
    user_id: str
    image_path: Optional[str] = None
    intent: Optional[Literal["parse_check", "ask_question", "show_plot"]] = None
    parsed_record: Optional[CheckRecord] = None
    plot_plan: Optional[PlotPlan] = None
    plot_path: Optional[str] = None
    answer: Optional[str] = None


llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0
)


def get_user_dataset_path(user_id: str):
    return os.path.join(BASE_DATA_FOLDER, f"user_{user_id}_spending.xlsx")


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def router_agent(state: AgentState):
    if state.image_path:
        return {"intent": "parse_check"}

    msg = state.user_message.lower()

    plot_keywords = [
        "plot", "chart", "graph", "visualize", "show all",
        "show my transactions", "histogram", "distribution",
        "pie chart", "bar chart", "line chart", "trend"
    ]

    if any(word in msg for word in plot_keywords):
        return {"intent": "show_plot"}

    return {"intent": "ask_question"}


def vision_parser_agent(state: AgentState):
    image_base64 = encode_image(state.image_path)
    structured_llm = llm.with_structured_output(CheckRecord)

    result = structured_llm.invoke([
        {
            "role": "system",
            "content": """
You are a financial document parser.

Extract:
- date
- merchant or payee
- amount
- category
- memo

If unclear, use null.

Use simple categories:
water, electricity, rent, groceries, insurance, medical, church, restaurant, gas, internet, phone, other.
"""
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract transaction information from this image."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        }
    ])

    return {"parsed_record": result}


def validation_agent(state: AgentState):
    record = state.parsed_record

    if record.amount is None:
        raise ValueError("Could not read amount from image.")

    if record.category is None:
        record.category = "other"

    return {"parsed_record": record}


def storage_agent(state: AgentState):
    dataset_path = get_user_dataset_path(state.user_id)
    file_hash = get_file_hash(state.image_path)

    record_dict = state.parsed_record.model_dump()
    record_dict["source_file"] = state.image_path
    record_dict["file_hash"] = file_hash

    new_row = pd.DataFrame([record_dict])

    if os.path.exists(dataset_path):
        old_data = pd.read_excel(dataset_path)

        if "file_hash" in old_data.columns:
            existing_hashes = set(old_data["file_hash"].astype(str))

            if file_hash in existing_hashes:
                return {
                    "answer": "Duplicate skipped. You already uploaded this receipt/check."
                }

        updated_data = pd.concat([old_data, new_row], ignore_index=True)
    else:
        updated_data = new_row

    updated_data.to_excel(dataset_path, index=False)

    return {
        "answer": (
            "Saved transaction:\n"
            f"Date: {record_dict.get('date')}\n"
            f"Merchant: {record_dict.get('merchant')}\n"
            f"Amount: ${record_dict.get('amount')}\n"
            f"Category: {record_dict.get('category')}"
        )
    }


def analytics_agent(state: AgentState):
    dataset_path = get_user_dataset_path(state.user_id)

    if not os.path.exists(dataset_path):
        return {"answer": "You have not uploaded any receipts/checks yet."}

    df = pd.read_excel(dataset_path)

    prompt = f"""
You are a personal spending analyst.

Only answer using this user's dataset.

Dataset:
{df.to_string(index=False)}

User question:
{state.user_message}

Answer clearly and calculate using the dataset.
"""

    result = llm.invoke(prompt)

    return {"answer": result.content}


def plot_planner_agent(state: AgentState):
    structured_llm = llm.with_structured_output(PlotPlan)

    result = structured_llm.invoke([
        {
            "role": "system",
            "content": """
You are a plotting planner.

Create a safe plot plan using only these dataset columns:
- date
- merchant
- amount
- category

Rules:
1. For historical transactions, use bar chart with date and amount.
2. For accumulated/cumulative spending, use line chart with date and amount and cumulative_sum.
3. For spending by category, use pie or bar chart grouped by category.
4. For spending by merchant, use bar chart grouped by merchant.
5. For distribution of amounts, use histogram using amount.
6. Never invent columns.
"""
        },
        {
            "role": "user",
            "content": state.user_message
        }
    ])

    return {"plot_plan": result}


def prepare_plot_data(df: pd.DataFrame, plan: PlotPlan):
    df = df.copy()

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df = df.dropna(subset=["amount"])

    if plan.chart_type != "histogram" and plan.x_column == "date":
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")

    if plan.aggregation == "none":
        plot_df = df

    elif plan.aggregation == "sum":
        plot_df = (
            df.groupby(plan.group_by)["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )

    elif plan.aggregation == "count":
        plot_df = (
            df.groupby(plan.group_by)
            .size()
            .reset_index(name="amount")
            .sort_values("amount", ascending=False)
        )

    elif plan.aggregation == "average":
        plot_df = (
            df.groupby(plan.group_by)["amount"]
            .mean()
            .reset_index()
            .sort_values("amount", ascending=False)
        )

    elif plan.aggregation == "cumulative_sum":
        df = df.sort_values("date")
        df["cumulative_amount"] = df["amount"].cumsum()
        plot_df = df
        plan.y_column = "amount"

    else:
        plot_df = df

    return plot_df


def chart_renderer_agent(state: AgentState):
    dataset_path = get_user_dataset_path(state.user_id)

    if not os.path.exists(dataset_path):
        return {"answer": "You have not uploaded any receipts/checks yet."}

    df = pd.read_excel(dataset_path)

    if df.empty:
        return {"answer": "Your spending dataset is empty."}

    plan = state.plot_plan
    plot_df = prepare_plot_data(df, plan)

    plot_path = os.path.join(PLOTS_FOLDER, f"user_{state.user_id}_{uuid.uuid4()}.png")

    plt.figure(figsize=(10, 6))

    if plan.chart_type == "bar":
        x = plot_df[plan.x_column].astype(str)
        y = plot_df["amount"]

        plt.bar(x, y)
        plt.xlabel(plan.x_column)
        plt.ylabel("Amount")
        plt.xticks(rotation=45, ha="right")

    elif plan.chart_type == "line":
        if plan.aggregation == "cumulative_sum":
            x = plot_df["date"].dt.strftime("%Y-%m-%d")
            y = plot_df["cumulative_amount"]
            plt.ylabel("Cumulative Amount")
        else:
            x = plot_df[plan.x_column].astype(str)
            y = plot_df["amount"]
            plt.ylabel("Amount")

        plt.plot(x, y, marker="o")
        plt.xlabel(plan.x_column or "date")
        plt.xticks(rotation=45, ha="right")

    elif plan.chart_type == "pie":
        x = plot_df[plan.group_by or plan.x_column].astype(str)
        y = plot_df["amount"]

        plt.pie(y, labels=x, autopct="%1.1f%%")
        plt.ylabel("")

    elif plan.chart_type == "histogram":
        plt.hist(plot_df["amount"], bins=10)
        plt.xlabel("Amount")
        plt.ylabel("Frequency")

    plt.title(plan.title)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    return {
        "answer": f"Created plot: {plan.title}",
        "plot_path": plot_path
    }


def route_after_router(state: AgentState):
    if state.intent == "parse_check":
        return "vision_parser_agent"

    if state.intent == "show_plot":
        return "plot_planner_agent"

    return "analytics_agent"


graph_builder = StateGraph(AgentState)

graph_builder.add_node("router_agent", router_agent)
graph_builder.add_node("vision_parser_agent", vision_parser_agent)
graph_builder.add_node("validation_agent", validation_agent)
graph_builder.add_node("storage_agent", storage_agent)
graph_builder.add_node("analytics_agent", analytics_agent)
graph_builder.add_node("plot_planner_agent", plot_planner_agent)
graph_builder.add_node("chart_renderer_agent", chart_renderer_agent)

graph_builder.add_edge(START, "router_agent")

graph_builder.add_conditional_edges(
    "router_agent",
    route_after_router,
    {
        "vision_parser_agent": "vision_parser_agent",
        "analytics_agent": "analytics_agent",
        "plot_planner_agent": "plot_planner_agent",
    }
)

graph_builder.add_edge("vision_parser_agent", "validation_agent")
graph_builder.add_edge("validation_agent", "storage_agent")
graph_builder.add_edge("storage_agent", END)

graph_builder.add_edge("analytics_agent", END)

graph_builder.add_edge("plot_planner_agent", "chart_renderer_agent")
graph_builder.add_edge("chart_renderer_agent", END)

app = graph_builder.compile()


def process_receipt_image(user_id: str, image_path: str):
    result = app.invoke({
        "user_message": "Save this receipt/check",
        "user_id": str(user_id),
        "image_path": image_path
    })

    return result


def ask_spending_question(user_id: str, question: str):
    result = app.invoke({
        "user_message": question,
        "user_id": str(user_id)
    })

    return result