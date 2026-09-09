import asyncio
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent
app = FastAPI(title="Legacy Credit Union Servicing Console")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")
MEMBERS = {"12345": "Jordan Example", "23456": "Casey Example"}
SCENARIOS = {"normal", "notice", "slow", "permission", "handoff", "expired"}


def render(request: Request, screen: str, **context: object) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="console.html", context={"screen": screen, **context}
    )


@app.get("/members", response_class=HTMLResponse)
async def search(request: Request, scenario: str = "normal") -> HTMLResponse:
    return render(
        request, "Member Search", scenario=scenario if scenario in SCENARIOS else "normal"
    )


@app.post("/members/search", response_class=HTMLResponse)
async def detail(
    request: Request,
    member_id: Annotated[str, Form()],
    scenario: Annotated[str, Form()] = "normal",
) -> HTMLResponse:
    if scenario == "slow":
        await asyncio.sleep(0.6)  # Intentional, deterministic demo latency; not a replay wait.
    if member_id == "40300" or scenario == "permission":
        return render(request, "Permission Denied")
    if scenario == "expired":
        return render(request, "Session Expired")
    if member_id not in MEMBERS:
        return render(request, "Member Not Found")
    return render(
        request,
        "Member Details",
        member_id=member_id,
        member_name=MEMBERS[member_id],
        scenario=scenario,
    )


@app.post("/accounts/new", response_class=HTMLResponse)
async def account(request: Request, member_id: Annotated[str, Form()]) -> HTMLResponse:
    if member_id not in MEMBERS:
        return render(request, "Member Not Found")
    return render(request, "Open New Sub-Account", member_id=member_id)


@app.post("/accounts/review", response_class=HTMLResponse)
async def review(
    request: Request,
    member_id: Annotated[str, Form()],
    account_type: Annotated[str, Form()],
    initial_deposit: Annotated[str, Form()],
) -> HTMLResponse:
    if member_id not in MEMBERS:
        return render(request, "Member Not Found")
    try:
        amount = Decimal(initial_deposit)
        valid = (
            amount.is_finite()
            and 0 < amount <= 100000
            and amount == amount.quantize(Decimal("0.01"))
        )
    except InvalidOperation:
        valid = False
    if not valid or account_type != "Savings":
        return render(
            request,
            "Open New Sub-Account",
            member_id=member_id,
            error="Enter a positive deposit up to 100000 with at most two decimal places.",
        )
    return render(
        request,
        "Review New Account",
        member_id=member_id,
        member_name=MEMBERS[member_id],
        amount=f"{amount:.2f}",
    )


@app.post("/accounts/create", response_class=HTMLResponse)
async def create(request: Request) -> HTMLResponse:
    return render(request, "Synthetic Account Created")


@app.get("/members/notice", response_class=HTMLResponse)
async def framed_notice() -> str:
    return '<p style="font:14px Arial">Training environment • All records are synthetic.</p>'
