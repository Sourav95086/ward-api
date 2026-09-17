from fastapi import FastAPI, HTTPException, Query
from supabase import create_client, Client
from dotenv import load_dotenv
from collections import defaultdict
from typing import Optional
from pydantic import BaseModel

import os
import smtplib
import ssl

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be present in .env"
    )


if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
    raise RuntimeError(
        "EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be present in .env"
    )


# ============================================================
# SUPABASE CLIENT
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Civic Reporter Ranking API",
    description="API for finding top civic issue reporters and sending contest emails",
    version="1.1.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Civic Reporter Ranking API is running"
    }


# ============================================================
# TOP 3 REPORTERS
# ============================================================

@app.get("/top-reporters")
def get_top_reporters(
    issue_location: str = Query(
        ...,
        description="Location of the civic issues, e.g. Bhubaneswar"
    )
):

    try:

        # --------------------------------------------------------
        # FETCH ALL ISSUES FOR THE LOCATION
        # --------------------------------------------------------

        response = (
            supabase
            .table("issue_reports")
            .select(
                """
                report_id,
                issue_id,
                issue_description,
                reported_by_name,
                reported_by_phone,
                reported_by_email,
                reported_on,
                issue_location,
                latitude,
                longitude,
                evidence
                """
            )
            .ilike(
                "issue_location",
                issue_location.strip()
            )
            .execute()
        )

        issues = response.data or []


        # --------------------------------------------------------
        # NO ISSUES
        # --------------------------------------------------------

        if not issues:

            return {
                "issue_location": issue_location,
                "total_issues": 0,
                "total_unique_reporters": 0,
                "top_reporters": []
            }


        # --------------------------------------------------------
        # GROUP REPORTS BY REPORTER
        # --------------------------------------------------------

        reporters = defaultdict(
            lambda: {
                "name": None,
                "phone": None,
                "email": None,
                "report_count": 0,
                "reports": []
            }
        )


        for issue in issues:

            name = issue.get(
                "reported_by_name"
            )

            phone = issue.get(
                "reported_by_phone"
            )

            email = issue.get(
                "reported_by_email"
            )


            # ----------------------------------------------------
            # CREATE UNIQUE REPORTER KEY
            # ----------------------------------------------------

            if phone and phone.strip():

                reporter_key = (
                    f"phone:{phone.strip()}"
                )

            elif email and email.strip():

                reporter_key = (
                    f"email:{email.strip().lower()}"
                )

            elif name and name.strip():

                reporter_key = (
                    f"name:{name.strip().lower()}"
                )

            else:

                reporter_key = (
                    f"anonymous:{issue.get('report_id')}"
                )


            # ----------------------------------------------------
            # STORE REPORTER INFORMATION
            # ----------------------------------------------------

            reporters[reporter_key]["name"] = name

            reporters[reporter_key]["phone"] = phone

            reporters[reporter_key]["email"] = email

            reporters[reporter_key]["report_count"] += 1


            # ----------------------------------------------------
            # STORE ISSUE INFORMATION
            # ----------------------------------------------------

            reporters[reporter_key]["reports"].append({

                "report_id": issue.get(
                    "report_id"
                ),

                "issue_id": issue.get(
                    "issue_id"
                ),

                "description": issue.get(
                    "issue_description"
                ),

                "reported_on": issue.get(
                    "reported_on"
                ),

                "location": issue.get(
                    "issue_location"
                ),

                "latitude": issue.get(
                    "latitude"
                ),

                "longitude": issue.get(
                    "longitude"
                ),

                "evidence": issue.get(
                    "evidence"
                )
            })


        # --------------------------------------------------------
        # SORT REPORTERS
        # --------------------------------------------------------

        sorted_reporters = sorted(
            reporters.values(),
            key=lambda x: x["report_count"],
            reverse=True
        )


        # --------------------------------------------------------
        # TOP 3
        # --------------------------------------------------------

        top_three = sorted_reporters[:3]


        # --------------------------------------------------------
        # BUILD RESPONSE
        # --------------------------------------------------------

        result = []


        for index, reporter in enumerate(
            top_three,
            start=1
        ):

            result.append({

                "rank": index,

                "name": reporter["name"],

                "phone": reporter["phone"],

                "email": reporter["email"],

                "report_count": reporter[
                    "report_count"
                ],

                "reports": reporter[
                    "reports"
                ]
            })


        # --------------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------------

        return {

            "issue_location": issue_location,

            "total_issues": len(issues),

            "total_unique_reporters": len(
                reporters
            ),

            "top_reporters": result
        }


    except Exception as e:

        print(
            "ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch reporter information: "
                + str(e)
            )
        )


# ============================================================
# EMAIL REQUEST MODEL
# ============================================================

class WinnerEmailRequest(BaseModel):

    email: str

    rank: int


# ============================================================
# GET REWARD BY RANK
# ============================================================

def get_reward(rank: int):

    if rank == 1:

        return "Amazon Gift Card"

    elif rank == 2:

        return "Flipkart Gift Card"

    elif rank == 3:

        return "Meesho Gift Card"

    else:

        return None


# ============================================================
# GET MEDAL BY RANK
# ============================================================

def get_medal(rank: int):

    if rank == 1:

        return "🥇"

    elif rank == 2:

        return "🥈"

    elif rank == 3:

        return "🥉"

    return "🏆"


# ============================================================
# CREATE EMAIL HTML
# ============================================================

def create_winner_email(
    email: str,
    rank: int,
    reward: str
):

    medal = get_medal(rank)


    html = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

</head>


<body style="
    margin:0;
    padding:0;
    background-color:#07111f;
    font-family:Arial,Helvetica,sans-serif;
">


<div style="
    max-width:650px;
    margin:30px auto;
    background-color:#0d1b2a;
    border-radius:18px;
    overflow:hidden;
    color:#ffffff;
">


    <!-- HEADER -->

    <div style="
        padding:35px 25px;
        text-align:center;
        background-color:#091625;
        border-bottom:1px solid #20364a;
    ">

        <div style="
            font-size:32px;
            font-weight:bold;
            color:#20d9ff;
        ">
            SNAPFIX
        </div>


        <div style="
            margin-top:8px;
            font-size:15px;
            color:#9db2c5;
            letter-spacing:1px;
        ">
            MONTHLY CONTEST
        </div>

    </div>


    <!-- CONTENT -->

    <div style="
        padding:35px 30px;
    ">


        <div style="
            text-align:center;
            font-size:48px;
        ">
            {medal}
        </div>


        <h1 style="
            text-align:center;
            font-size:27px;
            margin:15px 0;
        ">
            Congratulations!
        </h1>


        <p style="
            text-align:center;
            color:#b4c5d3;
            line-height:1.7;
            font-size:15px;
        ">

            You have been selected as one of the
            Top 3 reporters in this month's
            SnapFix Monthly Contest.

        </p>


        <!-- RANK -->

        <div style="
            margin-top:25px;
            padding:25px;
            text-align:center;
            background-color:#112438;
            border-radius:14px;
        ">


            <div style="
                color:#8ea6ba;
                font-size:13px;
                letter-spacing:1px;
            ">
                YOUR RANK
            </div>


            <div style="
                margin-top:8px;
                color:#20d9ff;
                font-size:38px;
                font-weight:bold;
            ">
                #{rank}
            </div>


        </div>


        <!-- REWARD -->

        <div style="
            margin-top:20px;
            padding:25px;
            text-align:center;
            background-color:#102d3d;
            border:1px solid #20d9ff;
            border-radius:14px;
        ">


            <div style="
                color:#9db2c5;
                font-size:13px;
                letter-spacing:1px;
            ">
                YOUR REWARD
            </div>


            <div style="
                margin-top:10px;
                color:#20d9ff;
                font-size:22px;
                font-weight:bold;
            ">
                {reward}
            </div>


        </div>


        <!-- MESSAGE -->

        <p style="
            margin-top:30px;
            color:#c3d0da;
            font-size:15px;
            line-height:1.8;
        ">

            Thank you for actively reporting civic
            issues through SnapFix.

        </p>


        <p style="
            color:#c3d0da;
            font-size:15px;
            line-height:1.8;
        ">

            Your contribution helps identify civic
            problems and supports efforts to make
            Bhubaneswar a better place.

        </p>


        <p style="
            margin-top:30px;
            text-align:center;
            color:#20d9ff;
            font-size:16px;
            font-weight:bold;
        ">

            See you in next month's SnapFix contest!

        </p>


    </div>


    <!-- FOOTER -->

    <div style="
        padding:22px;
        text-align:center;
        background-color:#091625;
        color:#71869a;
        font-size:12px;
    ">

        SnapFix Civic Reporting Platform

        <br><br>

        This is an automated email.

    </div>


</div>

</body>

</html>
"""


    return html


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(
    recipient_email: str,
    rank: int
):

    # --------------------------------------------------------
    # GET REWARD
    # --------------------------------------------------------

    reward = get_reward(rank)


    if reward is None:

        raise ValueError(
            "Rank must be 1, 2 or 3."
        )


    # --------------------------------------------------------
    # CREATE EMAIL
    # --------------------------------------------------------

    html_content = create_winner_email(
        recipient_email,
        rank,
        reward
    )


    # --------------------------------------------------------
    # CREATE MIME MESSAGE
    # --------------------------------------------------------

    message = MIMEMultipart(
        "alternative"
    )


    message["Subject"] = (
        "🎉 SnapFix Monthly Contest "
        "— Congratulations!"
    )

    message["From"] = EMAIL_ADDRESS

    message["To"] = recipient_email


    # --------------------------------------------------------
    # PLAIN TEXT VERSION
    # --------------------------------------------------------

    plain_text = f"""
SnapFix Monthly Contest

Congratulations!

You have been selected as one of the
Top 3 reporters in this month's
SnapFix Monthly Contest.

Rank: #{rank}

Reward: {reward}

Thank you for actively reporting civic
issues through SnapFix.

Your contribution helps identify civic
problems and supports efforts to make
Bhubaneswar a better place.

See you in next month's SnapFix contest!

SnapFix Civic Reporting Platform
"""


    # --------------------------------------------------------
    # ATTACH BOTH VERSIONS
    # --------------------------------------------------------

    message.attach(
        MIMEText(
            plain_text,
            "plain"
        )
    )


    message.attach(
        MIMEText(
            html_content,
            "html"
        )
    )


    # --------------------------------------------------------
    # GMAIL SMTP
    # --------------------------------------------------------

    context = ssl.create_default_context()


    with smtplib.SMTP(
        "smtp.gmail.com",
        587
    ) as server:

        server.starttls(
            context=context
        )

        server.login(
            EMAIL_ADDRESS,
            EMAIL_APP_PASSWORD
        )

        server.sendmail(
            EMAIL_ADDRESS,
            recipient_email,
            message.as_string()
        )


# ============================================================
# SEND WINNER EMAIL ROUTE
# ============================================================

@app.post("/send-winner-email")
def send_winner_email(
    request: WinnerEmailRequest
):

    # --------------------------------------------------------
    # VALIDATE EMAIL
    # --------------------------------------------------------

    if not request.email:

        raise HTTPException(
            status_code=400,
            detail="Email is required."
        )


    # --------------------------------------------------------
    # VALIDATE RANK
    # --------------------------------------------------------

    if request.rank not in [1, 2, 3]:

        raise HTTPException(
            status_code=400,
            detail="Rank must be 1, 2 or 3."
        )


    # --------------------------------------------------------
    # GET REWARD
    # --------------------------------------------------------

    reward = get_reward(
        request.rank
    )


    try:

        # ----------------------------------------------------
        # SEND EMAIL
        # ----------------------------------------------------

        send_email(
            recipient_email=request.email,
            rank=request.rank
        )


        return {

            "success": True,

            "message": (
                "Winner email sent successfully."
            ),

            "email": request.email,

            "rank": request.rank,

            "reward": reward
        }


    except Exception as e:

        print(
            "EMAIL ERROR:",
            str(e)
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to send winner email: "
                + str(e)
            )
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }