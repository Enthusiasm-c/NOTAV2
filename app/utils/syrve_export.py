from lxml import etree
import httpx
from app.config import settings
from app.utils.logger import logger

def build_xml(invoice_data: dict) -> str:
    root = etree.Element("SyrveDocument")
    etree.SubElement(root, "Supplier").text = invoice_data.get("supplier", "")
    etree.SubElement(root, "Buyer").text = invoice_data.get("buyer", "")
    etree.SubElement(root, "Date").text = invoice_data.get("date", "")
    items_elem = etree.SubElement(root, "Items")
    for pos in invoice_data.get("positions", []):
        item = etree.SubElement(items_elem, "Item")
        etree.SubElement(item, "Name").text = str(pos.get("name", ""))
        etree.SubElement(item, "Quantity").text = str(pos.get("quantity", ""))
        etree.SubElement(item, "Unit").text = str(pos.get("unit", ""))
        etree.SubElement(item, "Price").text = str(pos.get("price", ""))
        etree.SubElement(item, "Sum").text = str(pos.get("sum", ""))
    etree.SubElement(root, "TotalSum").text = str(invoice_data.get("total_sum", ""))
    return etree.tostring(root, pretty_print=True, encoding="utf-8").decode("utf-8")

async def post_to_syrve(xml_payload: str) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            headers = {
                "Content-Type": "application/xml",
                "Authorization": f"Bearer {settings.syrve_token or 'FAKE'}",
            }
            r = await client.post(settings.syrve_url, data=xml_payload, headers=headers)
            r.raise_for_status()
            return True, "Успех"
        except Exception as e:
            logger.error("Syrve export failed", error=str(e))
            return False, str(e)
