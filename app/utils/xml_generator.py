__all__ = ["generate_syrve_xml"]

from lxml import etree

def generate_syrve_xml(data: dict) -> str:
    """Генерирует XML-документ по схеме Syrve"""
    root = etree.Element("SyrveDocument")
    etree.SubElement(root, "Supplier").text = data.get("supplier_name", "")
    etree.SubElement(root, "Buyer").text = data.get("buyer_name", "")
    etree.SubElement(root, "Date").text = data.get("date", "")
    items_elem = etree.SubElement(root, "Items")
    for pos in data.get("positions", []):
        item = etree.SubElement(items_elem, "Item")
        etree.SubElement(item, "Name").text = str(pos.get("name", ""))
        etree.SubElement(item, "Quantity").text = str(pos.get("quantity", ""))
        etree.SubElement(item, "Unit").text = str(pos.get("unit", ""))
        etree.SubElement(item, "Price").text = str(pos.get("price", ""))
        etree.SubElement(item, "Sum").text = str(pos.get("sum", ""))
    etree.SubElement(root, "TotalSum").text = str(data.get("total_sum", ""))
    return etree.tostring(root, pretty_print=True, encoding="utf-8").decode("utf-8")
