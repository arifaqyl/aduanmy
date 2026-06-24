from pydantic import BaseModel


class ComplaintSchema(BaseModel):
    source_platform: str
    post_id: str
    url: str
    author_handle: str
    created_at: str
    raw_text: str
    normalized_text: str = ""
    detected_language_mix: str = ""
    category: str = ""
    subcategory: str = ""
    entity: str = ""
    location: str = ""
    severity: str = ""
    confidence: float = 0.0
    engagement: str = ""
    cluster_id: str = ""

