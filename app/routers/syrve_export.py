__all__ = ["export_to_syrve"]

import httpx
from app.config import settings
from app.utils.xml_generator import generate_syrve_xml

async def export_to_syrve(invoice_data: dict):
    """Генерирует XML, отправляет в Syrve, возвращает (bool, message)"""
    xml_data = generate_syrve_xml(invoice_data)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {
                "Content-Type": "application/xml",
                "Authorization": f"Bearer {settings.syrve_token or 'FAKE'}",
            }
            r = await client.post(settings.syrve_url, data=xml_data, headers=headers)
            r.raise_for_status()
            return True, "Success"
    except Exception as ex:
        return False, str(ex)
