from fastapi import APIRouter
from finer.api.routes.asset_builder import build_workflow_assets

router = APIRouter()

@router.get("")
async def get_stats():
    # Retrieve current counts for the major lifecycle stages
    intake = len(build_workflow_assets("intake"))
    library = len(build_workflow_assets("library"))
    # extraction = len(build_workflow_assets("extraction"))
    review = len(build_workflow_assets("review"))
    
    return {
        "success": True,
        "contract": "canonical_stats_v1",
        "pulse": {
            "intake": intake,
            "library": library,
            "review": review
        }
    }
