from fastapi import FastAPI, HTTPException, Query
from supabase import create_client, Client
from dotenv import load_dotenv
from pydantic import BaseModel
from collections import defaultdict
import os
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")


# ============================================================
# CHECK ENVIRONMENT VARIABLES
# ============================================================

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing from .env")

if not EMAIL_ADDRESS:
    raise RuntimeError("EMAIL_ADDRESS is missing from .env")

if not EMAIL_APP_PASSWORD:
    raise RuntimeError("EMAIL_APP_PASSWORD is missing from .env")


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
    title="SnapFix Civic Reporter API",
    description="SnapFix civic reporter ranking and contest email API",
    version="1.0.0"
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "SnapFix Civic Reporter API is running",
        "status": "online"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# TOP REPORTERS
# ============================================================

@app.get("/top-reporters")
def get_top_reporters(
    issue_location: str = Query(
        ...,
        description="Location of the civic issues, e.g. Bhubaneswar"
    )
):

    try:

        location = issue_location.strip()

        if not location:

            raise HTTPException(
                status_code=400,
                detail="issue_location cannot be empty"
            )


        # ====================================================
        # FETCH REPORTS
        # ====================================================

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
                location
            )
            .execute()
        )


        issues = response.data or []


        # ====================================================
        # NO REPORTS
        # ====================================================

        if not issues:

            return {
                "issue_location": location,
                "total_issues": 0,
                "total_unique_reporters": 0,
                "top_reporters": []
            }


        # ====================================================
        # GROUP REPORTS BY REPORTER
        # ====================================================

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

            name = issue.get("reported_by_name")
            phone = issue.get("reported_by_phone")
            email = issue.get("reported_by_email")


            # ------------------------------------------------
            # IDENTIFY REPORTER
            # ------------------------------------------------

            if phone and str(phone).strip():

                reporter_key = (
                    f"phone:{str(phone).strip()}"
                )

            elif email and str(email).strip():

                reporter_key = (
                    f"email:{str(email).strip().lower()}"
                )

            elif name and str(name).strip():

                reporter_key = (
                    f"name:{str(name).strip().lower()}"
                )

            else:

                reporter_key = (
                    f"anonymous:{issue.get('report_id')}"
                )


            # ------------------------------------------------
            # SAVE REPORTER DETAILS
            # ------------------------------------------------

            reporters[reporter_key]["name"] = name

            reporters[reporter_key]["phone"] = phone

            reporters[reporter_key]["email"] = email

            reporters[reporter_key]["report_count"] += 1


            # ------------------------------------------------
            # SAVE REPORT
            # ------------------------------------------------

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


        # ====================================================
        # SORT REPORTERS
        # ====================================================

        sorted_reporters = sorted(
            reporters.values(),
            key=lambda x: x["report_count"],
            reverse=True
        )


        # ====================================================
        # TAKE TOP 3
        # ====================================================

        top_three = sorted_reporters[:3]


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


        # ====================================================
        # RESPONSE
        # ====================================================

        return {

            "issue_location": location,

            "total_issues": len(issues),

            "total_unique_reporters": len(
                reporters
            ),

            "top_reporters": result

        }


    except HTTPException:

        raise


    except Exception as e:

        print(
            "TOP REPORTERS ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch reporter "
                f"information: {str(e)}"
            )
        )


# ============================================================
# WINNER EMAIL REQUEST MODEL
# ============================================================

class WinnerEmailRequest(BaseModel):

    email: str

    rank: int


# ============================================================
# REWARD MAPPING
# ============================================================

def get_reward(rank: int):

    rewards = {

        1: "Amazon Gift Card",

        2: "Flipkart Gift Card",

        3: "Meesho Gift Card"

    }

    return rewards.get(rank)


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(
    recipient_email: str,
    rank: int
):

    # ========================================================
    # GET REWARD
    # ========================================================

    reward = get_reward(rank)

    if reward is None:

        raise ValueError(
            "Invalid rank. Rank must be 1, 2 or 3."
        )


    # ========================================================
    # SUBJECT
    # ========================================================

    subject = (
        "Congratulations! You are a "
        "SnapFix Monthly Contest Winner"
    )


    # ========================================================
    # HTML EMAIL
    # ========================================================

    html = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>
SnapFix Monthly Contest
</title>

</head>


<body
style="
margin:0;
padding:0;
background:#07111f;
font-family:Arial,Helvetica,sans-serif;
">


<div
style="
max-width:600px;
margin:40px auto;
background:#0d1b2a;
border-radius:18px;
overflow:hidden;
border:1px solid #18324a;
"
>


<!-- HEADER -->

<div
style="
padding:30px;
text-align:center;
background:#081522;
"
>

<h1
style="
margin:0;
color:#00e5ff;
font-size:30px;
letter-spacing:2px;
"
>
SNAPFIX
</h1>


<p
style="
color:#8fa7bd;
margin-top:8px;
font-size:14px;
"
>
Monthly Civic Reporter Contest
</p>

</div>


<!-- CONTENT -->

<div
style="
padding:35px 30px;
color:white;
"
>


<h2
style="
color:#00e5ff;
margin-top:0;
"
>
Congratulations!
</h2>


<p
style="
color:#d7e3ee;
font-size:16px;
line-height:1.7;
"
>

You have been selected as one of the
top contributors in this month's
SnapFix civic reporting contest.

</p>


<!-- WINNER INFORMATION -->

<div
style="
background:#102438;
border-radius:14px;
padding:22px;
margin:25px 0;
"
>


<p
style="
margin:8px 0;
color:#91a8bd;
"
>
Your Rank
</p>


<p
style="
margin:0;
font-size:32px;
font-weight:bold;
color:#00e5ff;
"
>
#{rank}
</p>


<p
style="
margin-top:20px;
margin-bottom:8px;
color:#91a8bd;
"
>
Your Reward
</p>


<p
style="
margin:0;
font-size:20px;
font-weight:bold;
color:white;
"
>
{reward}
</p>


</div>


<p
style="
color:#d7e3ee;
font-size:15px;
line-height:1.7;
"
>

Thank you for helping SnapFix identify
and report important civic issues
in your community.

</p>


<p
style="
color:#d7e3ee;
font-size:15px;
line-height:1.7;
"
>

Your contribution helps authorities
understand civic problems and
prioritize improvements.

</p>


<!-- FOOTER -->

<div
style="
margin-top:30px;
padding-top:20px;
border-top:1px solid #20384d;
text-align:center;
"
>

<p
style="
color:#00e5ff;
font-weight:bold;
"
>

See you in next month's
SnapFix contest!

</p>

</div>


</div>

</div>

</body>

</html>
"""


    # ========================================================
    # CREATE MESSAGE
    # ========================================================

    message = MIMEMultipart(
        "alternative"
    )

    message["From"] = EMAIL_ADDRESS

    message["To"] = recipient_email

    message["Subject"] = subject


    message.attach(
        MIMEText(
            html,
            "html"
        )
    )


    # ========================================================
    # GMAIL SMTP
    # ========================================================

    print()
    print(
        "========================================"
    )
    print(
        "CONNECTING TO GMAIL SMTP"
    )
    print(
        "========================================"
    )


    with smtplib.SMTP(
        "smtp.gmail.com",
        587,
        timeout=30
    ) as server:

        server.ehlo()

        print(
            "Starting TLS..."
        )

        server.starttls()

        server.ehlo()

        print(
            "Logging into Gmail..."
        )

        server.login(
            EMAIL_ADDRESS,
            EMAIL_APP_PASSWORD
        )

        print(
            "Sending email..."
        )

        server.sendmail(
            EMAIL_ADDRESS,
            recipient_email,
            message.as_string()
        )


    print(
        "EMAIL SENT SUCCESSFULLY"
    )

    print(
        "Recipient:",
        recipient_email
    )

    print(
        "Rank:",
        rank
    )

    print(
        "Reward:",
        reward
    )

    print(
        "========================================"
    )


    return reward


# ============================================================
# SEND WINNER EMAIL ENDPOINT
# ============================================================

@app.post("/send-winner-email")
def send_winner_email(
    request: WinnerEmailRequest
):

    try:

        # ----------------------------------------------------
        # CHECK EMAIL
        # ----------------------------------------------------

        email = request.email.strip()

        if not email:

            raise HTTPException(
                status_code=400,
                detail="Email is required"
            )


        # ----------------------------------------------------
        # CHECK RANK
        # ----------------------------------------------------

        if request.rank not in [1, 2, 3]:

            raise HTTPException(
                status_code=400,
                detail="Rank must be 1, 2 or 3"
            )


        print()
        print(
            "========================================"
        )
        print(
            "WINNER EMAIL REQUEST"
        )
        print(
            "========================================"
        )

        print(
            "Email:",
            email
        )

        print(
            "Rank:",
            request.rank
        )


        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        reward = send_email(
            recipient_email=email,
            rank=request.rank
        )


        # ----------------------------------------------------
        # RETURN RESPONSE
        # ----------------------------------------------------

        return {

            "success": True,

            "message":
                "Winner email sent successfully.",

            "email":
                email,

            "rank":
                request.rank,

            "reward":
                reward

        }


    except HTTPException:

        raise


    except Exception as e:

        print()
        print(
            "========================================"
        )
        print(
            "EMAIL ERROR"
        )
        print(
            "========================================"
        )

        print(
            str(e)
        )

        print(
            "========================================"
        )


        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to send winner email: "
                f"{str(e)}"
            )
        )


# ============================================================
# RUN APPLICATION DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )