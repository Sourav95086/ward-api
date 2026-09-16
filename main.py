from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY is missing from .env")


# ============================================================
# SUPABASE CONNECTION
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Ward Information API",
    description="Returns ward-wise civic issue information",
    version="1.0.0"
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "status": "success",
        "message": "Ward Information API is running"
    }


# ============================================================
# GET WARD INFORMATION
# ============================================================

@app.get("/ward-info/{city}")
def get_ward_info(city: str):

    try:

        # ----------------------------------------------------
        # FETCH DATA FROM SUPABASE
        # ----------------------------------------------------

        response = (
            supabase
            .table("ward_issue_summary")
            .select(
                "id,city,ward_number,issue_category,issue_count,created_at,updated_at"
            )
            .eq("city", city)
            .order("ward_number", desc=False)
            .execute()
        )

        data = response.data

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No ward information found for {city}"
            )


        # ----------------------------------------------------
        # GROUP DATA BY WARD
        # ----------------------------------------------------

        wards = {}

        for row in data:

            ward_number = row["ward_number"]

            if ward_number not in wards:

                wards[ward_number] = {
                    "ward_number": ward_number,
                    "issues": [],
                    "total_issues": 0
                }

            issue_count = row.get("issue_count") or 0

            wards[ward_number]["issues"].append({
                "issue_category": row["issue_category"],
                "issue_count": issue_count
            })

            wards[ward_number]["total_issues"] += issue_count


        # ----------------------------------------------------
        # CONVERT DICT TO LIST
        # ----------------------------------------------------

        ward_list = list(wards.values())


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "city": city,
            "total_wards": len(ward_list),
            "wards": ward_list
        }


    except HTTPException:
        raise

    except Exception as e:

        print("ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch ward information"
        )