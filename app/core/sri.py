"""SRI Helper module for generating access keys and XML invoices."""

from __future__ import annotations

import random
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Any


def generate_verificator_digit(access_key: str) -> int:
    """Ecuadorian modulo 11 algorithm for verification digit."""
    addition = 0
    multiple = 7
    for char in access_key:
        addition += int(char) * multiple
        multiple = 7 if multiple <= 2 else (multiple - 1)
    
    result = 11 - (addition % 11)
    if result == 10:
        return 1
    if result == 11:
        return 0
    return result


def generate_access_key(
    date_str: str,
    cod_doc: str,
    ruc: str,
    environment: str,
    establishment: str,
    emission_point: str,
    sequential: str,
    numeric_code: str | None = None,
    emission_type: str = "1"
) -> str:
    """Generates a 49-digit access key for the SRI document."""
    # Ensure numeric_code is 8 digits
    if not numeric_code:
        numeric_code = f"{random.randint(10000000, 99999999):08d}"
    else:
        numeric_code = f"{int(numeric_code):08d}"

    # Pad inputs to correct lengths
    establishment = f"{int(establishment):03d}"
    emission_point = f"{int(emission_point):03d}"
    sequential = f"{int(sequential):09d}"

    key_base = f"{date_str}{cod_doc}{ruc}{environment}{establishment}{emission_point}{sequential}{numeric_code}{emission_type}"
    digit = generate_verificator_digit(key_base)
    return f"{key_base}{digit}"


def build_sri_xml(invoice: Any, client: Any | None, settings: Any, preloaded_details: list | None = None) -> str:

    """Builds the Ecuadorian electronic invoice XML matching open-factura structure."""
    issue_date = invoice.issue_date or datetime.now()
    date_str_ddmmyyyy = issue_date.strftime("%d%m%Y")
    date_str_slash = issue_date.strftime("%d/%m/%Y")

    # Sequential number from invoice_number
    # invoice.invoice_number is e.g. "INV-000010"
    seq_number = "000000001"
    if invoice.invoice_number:
        digits = "".join(c for c in invoice.invoice_number if c.isdigit())
        if digits:
            seq_number = f"{int(digits):09d}"

    access_key = invoice.clave_acceso_snapshot
    if not access_key:
        access_key = generate_access_key(
            date_str=date_str_ddmmyyyy,
            cod_doc="01",
            ruc=settings.merchant_ruc,
            environment="1" if settings.env == "dev" else "2",
            establishment="001",
            emission_point="001",
            sequential=seq_number
        )

    # Buyer info
    if client:
        buyer_id = client.cedula or "9999999999999"
        # 04: RUC, 05: Cédula, 06: Pasaporte, 07: Consumidor final
        if buyer_id == "9999999999999":
            buyer_type = "07"
            buyer_name = "CONSUMIDOR FINAL"
            buyer_address = "N/A"
        else:
            buyer_type = "04" if len(buyer_id) == 13 else ("05" if len(buyer_id) == 10 else "06")
            buyer_name = f"{(client.first_name or '').strip()} {(client.last_name or '').strip()}".strip()
            buyer_address = client.address or "N/A"
    else:
        buyer_id = "9999999999999"
        buyer_type = "07"
        buyer_name = "CONSUMIDOR FINAL"
        buyer_address = "N/A"

    factura = ET.Element(
        "factura",
        attrib={
            "id": "comprobante",
            "version": "1.0.0",
            "xmlns:ds": "http://www.w3.org/2000/09/xmldsig#",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }
    )

    # infoTributaria
    info_trib = ET.SubElement(factura, "infoTributaria")
    ET.SubElement(info_trib, "ambiente").text = "1" if settings.env == "dev" else "2"
    ET.SubElement(info_trib, "tipoEmision").text = "1"
    ET.SubElement(info_trib, "razonSocial").text = settings.merchant_name
    ET.SubElement(info_trib, "nombreComercial").text = settings.merchant_name
    ET.SubElement(info_trib, "ruc").text = settings.merchant_ruc
    ET.SubElement(info_trib, "claveAcceso").text = access_key
    ET.SubElement(info_trib, "codDoc").text = "01"
    ET.SubElement(info_trib, "estab").text = "001"
    ET.SubElement(info_trib, "ptoEmi").text = "001"
    ET.SubElement(info_trib, "secuencial").text = seq_number
    ET.SubElement(info_trib, "dirMatriz").text = settings.merchant_address

    # infoFactura
    info_fac = ET.SubElement(factura, "infoFactura")
    ET.SubElement(info_fac, "fechaEmision").text = date_str_slash
    ET.SubElement(info_fac, "dirEstablecimiento").text = settings.merchant_address
    ET.SubElement(info_fac, "obligadoContabilidad").text = settings.merchant_obligado_contabilidad
    ET.SubElement(info_fac, "tipoIdentificacionComprador").text = buyer_type
    ET.SubElement(info_fac, "razonSocialComprador").text = buyer_name
    ET.SubElement(info_fac, "identificacionComprador").text = buyer_id
    ET.SubElement(info_fac, "direccionComprador").text = buyer_address
    ET.SubElement(info_fac, "totalSinImpuestos").text = f"{invoice.subtotal_snapshot:.2f}"
    ET.SubElement(info_fac, "totalDescuento").text = "0.00"

    # Group taxes by rate to compute totals
    total_con_impuestos = ET.SubElement(info_fac, "totalConImpuestos")

    details_to_use = preloaded_details if preloaded_details is not None else (invoice.details or [])

    tax_groups: dict[Decimal, dict[str, Decimal]] = {}
    for detail in details_to_use:
        for dt in getattr(detail, "detail_taxes", []):
            rate = dt.rate_snapshot or Decimal("0")
            if rate not in tax_groups:
                tax_groups[rate] = {"base": Decimal("0.00"), "value": Decimal("0.00")}
            # Base of tax for this detail item is price * quantity
            qty = detail.quantity or 0
            price = detail.unit_price_snapshot or Decimal("0")
            tax_groups[rate]["base"] += Decimal(str(price)) * Decimal(qty)
            tax_groups[rate]["value"] += Decimal(str(dt.calculated_amount_snapshot or 0))

    # If no taxes found, fallback to 0%
    if not tax_groups:
        tax_groups[Decimal("0.00")] = {"base": invoice.subtotal_snapshot or Decimal("0.00"), "value": Decimal("0.00")}

    for rate, totals in tax_groups.items():
        percent_code = "0"
        if rate == Decimal("12.00"):
            percent_code = "2"
        elif rate == Decimal("14.00"):
            percent_code = "3"
        elif rate == Decimal("15.00"):
            percent_code = "4"
        elif rate == Decimal("5.00"):
            percent_code = "5"

        tot_imp = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(tot_imp, "codigo").text = "2"  # IVA
        ET.SubElement(tot_imp, "codigoPorcentaje").text = percent_code
        ET.SubElement(tot_imp, "baseImponible").text = f"{totals['base']:.2f}"
        ET.SubElement(tot_imp, "tarifa").text = f"{rate:.2f}"
        ET.SubElement(tot_imp, "valor").text = f"{totals['value']:.2f}"

    ET.SubElement(info_fac, "propina").text = "0.00"
    ET.SubElement(info_fac, "importeTotal").text = f"{invoice.total_snapshot:.2f}"
    ET.SubElement(info_fac, "moneda").text = "DOLAR"

    # pagos
    pagos = ET.SubElement(info_fac, "pagos")
    pago = ET.SubElement(pagos, "pago")
    ET.SubElement(pago, "formaPago").text = "01"  # Cash / sin utilización del sistema financiero
    ET.SubElement(pago, "total").text = f"{invoice.total_snapshot:.2f}"

    # detalles
    detalles = ET.SubElement(factura, "detalles")
    for detail in details_to_use:
        det = ET.SubElement(detalles, "detalle")
        prod_code = f"PROD{detail.product_id:03d}" if detail.product_id else "PROD000"
        ET.SubElement(det, "codigoPrincipal").text = prod_code
        ET.SubElement(det, "descripcion").text = detail.product_name or "Desconocido"
        qty = detail.quantity or 0
        price = detail.unit_price_snapshot or Decimal("0")
        ET.SubElement(det, "cantidad").text = f"{qty:.6f}"
        ET.SubElement(det, "precioUnitario").text = f"{price:.6f}"
        ET.SubElement(det, "descuento").text = "0.00"
        line_sub = Decimal(str(price)) * Decimal(qty)
        ET.SubElement(det, "precioTotalSinImpuesto").text = f"{line_sub:.2f}"

        det_imps = ET.SubElement(det, "impuestos")
        detail_taxes = getattr(detail, "detail_taxes", [])
        
        # If detail has no taxes, default to 0%
        if not detail_taxes:
            det_imp = ET.SubElement(det_imps, "impuesto")
            ET.SubElement(det_imp, "codigo").text = "2"
            ET.SubElement(det_imp, "codigoPorcentaje").text = "0"
            ET.SubElement(det_imp, "tarifa").text = "0.00"
            ET.SubElement(det_imp, "baseImponible").text = f"{line_sub:.2f}"
            ET.SubElement(det_imp, "valor").text = "0.00"
        else:
            for dt in detail_taxes:
                rate = dt.rate_snapshot or Decimal("0")
                percent_code = "0"
                if rate == Decimal("12.00"):
                    percent_code = "2"
                elif rate == Decimal("14.00"):
                    percent_code = "3"
                elif rate == Decimal("15.00"):
                    percent_code = "4"
                elif rate == Decimal("5.00"):
                    percent_code = "5"

                det_imp = ET.SubElement(det_imps, "impuesto")
                ET.SubElement(det_imp, "codigo").text = "2"  # IVA
                ET.SubElement(det_imp, "codigoPorcentaje").text = percent_code
                ET.SubElement(det_imp, "tarifa").text = f"{rate:.2f}"
                ET.SubElement(det_imp, "baseImponible").text = f"{line_sub:.2f}"
                ET.SubElement(det_imp, "valor").text = f"{dt.calculated_amount_snapshot or 0:.2f}"

    return ET.tostring(factura, encoding="unicode")
