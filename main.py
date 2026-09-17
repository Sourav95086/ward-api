from fastapi import FastAPI, HTTPException, Query
from supabase import create_client, Client
from dotenv import load_dotenv
from collections import defaultdict
from typing import Optional
import os

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be present in .env"
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
    description="API for finding the top civic issue reporters by location",
    version="1.0.0"
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
            .ilike("issue_location", issue_location.strip())
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
                "top_reporters": []
            }

        # --------------------------------------------------------
        # GROUP REPORTS BY REPORTER
        #
        # Phone number is used as the primary identity.
        # If phone is missing, email is used.
        # If both are missing, name is used.
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

            name = issue.get("reported_by_name")
            phone = issue.get("reported_by_phone")
            email = issue.get("reported_by_email")

            # ----------------------------------------------------
            # CREATE UNIQUE REPORTER KEY
            # ----------------------------------------------------

            if phone and phone.strip():
                reporter_key = f"phone:{phone.strip()}"

            elif email and email.strip():
                reporter_key = f"email:{email.strip().lower()}"

            elif name and name.strip():
                reporter_key = f"name:{name.strip().lower()}"

            else:
                # Completely anonymous report
                reporter_key = f"anonymous:{issue.get('report_id')}"

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
                "report_id": issue.get("report_id"),
                "issue_id": issue.get("issue_id"),
                "description": issue.get("issue_description"),
                "reported_on": issue.get("reported_on"),
                "location": issue.get("issue_location"),
                "latitude": issue.get("latitude"),
                "longitude": issue.get("longitude"),
                "evidence": issue.get("evidence")
            })

        # --------------------------------------------------------
        # SORT REPORTERS BY NUMBER OF REPORTS
        # --------------------------------------------------------

        sorted_reporters = sorted(
            reporters.values(),
            key=lambda x: x["report_count"],
            reverse=True
        )

        # --------------------------------------------------------
        # TAKE TOP 3
        # --------------------------------------------------------

        top_three = sorted_reporters[:3]

        # --------------------------------------------------------
        # BUILD RESPONSE
        # --------------------------------------------------------

        result = []

        for index, reporter in enumerate(top_three, start=1):

            result.append({
                "rank": index,
                "name": reporter["name"],
                "phone": reporter["phone"],
                "email": reporter["email"],
                "report_count": reporter["report_count"],
                "reports": reporter["reports"]
            })

        # --------------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------------

        return {
            "issue_location": issue_location,
            "total_issues": len(issues),
            "total_unique_reporters": len(reporters),
            "top_reporters": result
        }

    except Exception as e:

        print("ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch reporter information: {str(e)}"
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }