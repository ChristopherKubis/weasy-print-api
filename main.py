from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import weasyprint
import io

app = FastAPI(
    title="HTML to PDF API",
    description="API to convert HTML content to PDF using WeasyPrint",
    version="1.0.0",
)


class HTMLRequest(BaseModel):
    html: str

    class Config:
        json_schema_extra = {
            "example": {
                "html": "<html><body><h1>Hello World</h1><p>This is a test PDF.</p></body></html>"
            }
        }


@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint
    """
    return {"message": "HTML to PDF API is running", "status": "healthy"}


@app.post("/convert/html-to-pdf", tags=["Conversion"], response_class=Response)
async def convert_html_to_pdf(request: HTMLRequest):
    """
    Convert HTML content to PDF

    - **html**: HTML string to convert to PDF

    Returns a PDF file as binary content
    """
    try:
        # Convert HTML to PDF using WeasyPrint
        html_doc = weasyprint.HTML(string=request.html)
        pdf_bytes = html_doc.write_pdf()

        # Return PDF as response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=output.pdf"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error converting HTML to PDF: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
