"""PdfService — invoice PDF generation with ReportLab.

Renders an official-looking Ecuadorian SRI RIDE PDF layout:
  - Double-column header: matrix info on the left, RUC / access key / barcode on the right.
  - Client / transaction details in the middle.
  - Line items table (Code, Qty, Description, Unit Price, Descuento, Total).
  - Bottom section: Payment method details on the left, Tax breakdown and totals on the right.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import get_settings


def _fmt_money(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


class PdfService:
    def render_invoice(self, invoice: Any) -> bytes:
        settings = get_settings()
        buf = io.BytesIO()
        
        # A4 margins: 10mm all sides to maximize space
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
            title=f"Factura {invoice.invoice_number or invoice.id}",
        )
        
        styles = getSampleStyleSheet()
        
        # custom paragraph styles
        h1 = ParagraphStyle("h1", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=15)
        bold_p = ParagraphStyle("bold_p", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11)
        normal_p = ParagraphStyle("normal_p", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11)
        small_p = ParagraphStyle("small_p", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10)
        micro_p = ParagraphStyle("micro_p", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=8)

        story: list[Any] = []

        # 1. Parse XML or fallback to DB snapshots
        xml_data: dict[str, Any] = {}
        if invoice.sri_xml_snapshot:
            try:
                root = ET.fromstring(invoice.sri_xml_snapshot)
                
                # infoTributaria
                info_trib = root.find("infoTributaria")
                if info_trib is not None:
                    xml_data["ambiente"] = info_trib.findtext("ambiente")
                    xml_data["tipoEmision"] = info_trib.findtext("tipoEmision")
                    xml_data["razonSocial"] = info_trib.findtext("razonSocial")
                    xml_data["nombreComercial"] = info_trib.findtext("nombreComercial")
                    xml_data["ruc"] = info_trib.findtext("ruc")
                    xml_data["claveAcceso"] = info_trib.findtext("claveAcceso")
                    xml_data["estab"] = info_trib.findtext("estab")
                    xml_data["ptoEmi"] = info_trib.findtext("ptoEmi")
                    xml_data["secuencial"] = info_trib.findtext("secuencial")
                    xml_data["dirMatriz"] = info_trib.findtext("dirMatriz")
                
                # infoFactura
                info_fac = root.find("infoFactura")
                if info_fac is not None:
                    xml_data["fechaEmision"] = info_fac.findtext("fechaEmision")
                    xml_data["dirEstablecimiento"] = info_fac.findtext("dirEstablecimiento")
                    xml_data["obligadoContabilidad"] = info_fac.findtext("obligadoContabilidad")
                    xml_data["tipoIdentificacionComprador"] = info_fac.findtext("tipoIdentificacionComprador")
                    xml_data["razonSocialComprador"] = info_fac.findtext("razonSocialComprador")
                    xml_data["identificacionComprador"] = info_fac.findtext("identificacionComprador")
                    xml_data["direccionComprador"] = info_fac.findtext("direccionComprador")
                    xml_data["totalSinImpuestos"] = info_fac.findtext("totalSinImpuestos")
                    xml_data["totalDescuento"] = info_fac.findtext("totalDescuento")
                    xml_data["propina"] = info_fac.findtext("propina")
                    xml_data["importeTotal"] = info_fac.findtext("importeTotal")
                    
                    # collect tax groups
                    tax_groups = []
                    tot_imps = info_fac.find("totalConImpuestos")
                    if tot_imps is not None:
                        for ti in tot_imps.findall("totalImpuesto"):
                            tax_groups.append({
                                "codigo": ti.findtext("codigo"),
                                "codigoPorcentaje": ti.findtext("codigoPorcentaje"),
                                "baseImponible": ti.findtext("baseImponible"),
                                "tarifa": ti.findtext("tarifa"),
                                "valor": ti.findtext("valor")
                            })
                    xml_data["tax_groups"] = tax_groups
                    
                    # payments
                    payments = []
                    pags = info_fac.find("pagos")
                    if pags is not None:
                        for p in pags.findall("pago"):
                            payments.append({
                                "formaPago": p.findtext("formaPago"),
                                "total": p.findtext("total")
                            })
                    xml_data["payments"] = payments
                
                # detalles
                detalles_list = []
                dets = root.find("detalles")
                if dets is not None:
                    for d in dets.findall("detalle"):
                        detalles_list.append({
                            "codigoPrincipal": d.findtext("codigoPrincipal"),
                            "descripcion": d.findtext("descripcion"),
                            "cantidad": d.findtext("cantidad"),
                            "precioUnitario": d.findtext("precioUnitario"),
                            "descuento": d.findtext("descuento"),
                            "precioTotalSinImpuesto": d.findtext("precioTotalSinImpuesto")
                        })
                xml_data["detalles"] = detalles_list
                
            except Exception:
                # fall through to DB mapping
                xml_data = {}

        # 2. Extract Header details (XML or DB fallback)
        ruc = xml_data.get("ruc") or settings.merchant_ruc
        razon_social = xml_data.get("razonSocial") or settings.merchant_name
        dir_matriz = xml_data.get("dirMatriz") or settings.merchant_address
        dir_estab = xml_data.get("dirEstablecimiento") or settings.merchant_address
        obligado = xml_data.get("obligadoContabilidad") or settings.merchant_obligado_contabilidad
        
        # sequential invoice number: e.g. 001-001-000000100
        estab = xml_data.get("estab") or "001"
        pto_emi = xml_data.get("ptoEmi") or "001"
        if xml_data.get("secuencial"):
            seq = xml_data["secuencial"]
        else:
            digits = "".join(c for c in (invoice.invoice_number or "") if c.isdigit())
            seq = f"{int(digits):09d}" if digits else f"{invoice.id:09d}"
        invoice_seq_number = f"{estab}-{pto_emi}-{seq}"
        
        # access key
        access_key = xml_data.get("claveAcceso") or invoice.clave_acceso_snapshot or ""
        ambiente_label = "PRUEBAS" if (xml_data.get("ambiente") == "1" or settings.env == "dev") else "PRODUCCIÓN"
        emision_label = "NORMAL"

        # Client details
        client_name = xml_data.get("razonSocialComprador") or invoice.client_name_snapshot or "Consumidor final"
        client_id = xml_data.get("identificacionComprador") or invoice.client_cedula_snapshot or "9999999999999"
        client_address = xml_data.get("direccionComprador") or invoice.client_address_snapshot or "N/A"
        client_phone = invoice.client_phone_snapshot or "N/A"
        issue_date_str = xml_data.get("fechaEmision") or (
            inv_date.strftime("%d/%m/%Y")
            if isinstance(inv_date := (
                datetime.fromisoformat(invoice.issue_date) if invoice.issue_date else datetime.now()
            ), datetime)
            else "-"
        )

        # 3. Build Header Layout (Logo & Matriz vs RUC & Access Key Box)
        # Left Box (Logo, Merchant Info)
        merchant_info = [
            Paragraph(f"<b>{razon_social}</b>", h1),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Dirección Matriz:</b> {dir_matriz}", small_p),
            Paragraph(f"<b>Dirección Sucursal:</b> {dir_estab}", small_p),
            Spacer(1, 1 * mm),
            Paragraph(f"<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {obligado}", bold_p),
        ]
        left_table = Table([[merchant_info]], colWidths=[90 * mm])
        left_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        # Right Box (RUC, Access Key, Barcode)
        barcode_drawing = Drawing(160, 35)
        if access_key:
            try:
                # scale Code 128 to fit box
                barcode = code128.Code128(access_key, barHeight=25, barWidth=0.7)
                barcode_drawing.add(barcode)
            except Exception:
                pass

        right_info = [
            Paragraph(f"<b>R.U.C.:</b> {ruc}", bold_p),
            Spacer(1, 1 * mm),
            Paragraph("<b>F A C T U R A</b>", bold_p),
            Paragraph(f"No. {invoice_seq_number}", bold_p),
            Spacer(1, 1 * mm),
            Paragraph(f"<b>NÚMERO DE AUTORIZACIÓN:</b><br/>{access_key or 'PENDIENTE'}", small_p),
            Spacer(1, 1 * mm),
            Paragraph(f"<b>AMBIENTE:</b> {ambiente_label}", small_p),
            Paragraph(f"<b>EMISIÓN:</b> {emision_label}", small_p),
            Spacer(1, 1.5 * mm),
            Paragraph("<b>CLAVE DE ACCESO:</b>", bold_p),
            barcode_drawing,
            Paragraph(access_key, micro_p),
        ]
        right_table = Table([[right_info]], colWidths=[95 * mm])
        right_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        # Outer Header Table
        header_table = Table([[left_table, right_table]], colWidths=[92 * mm, 98 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 4 * mm))

        # 4. Client / Transaction Box
        client_info = [
            [
                Paragraph(f"<b>Razón Social / Nombres y Apellidos:</b> {client_name}", normal_p),
                Paragraph(f"<b>Identificación:</b> {client_id}", normal_p)
            ],
            [
                Paragraph(f"<b>Fecha Emisión:</b> {issue_date_str}", normal_p),
                Paragraph(f"<b>Teléfono:</b> {client_phone}", normal_p)
            ],
            [
                Paragraph(f"<b>Dirección:</b> {client_address}", normal_p),
                Paragraph("", normal_p) # Empty cell to balance layout
            ]
        ]
        client_table = Table(client_info, colWidths=[120 * mm, 70 * mm])
        client_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(client_table)
        story.append(Spacer(1, 4 * mm))

        # 5. Line Items Table
        items_rows = [
            [
                Paragraph("<b>Cod. Principal</b>", bold_p),
                Paragraph("<b>Cant.</b>", bold_p),
                Paragraph("<b>Descripción</b>", bold_p),
                Paragraph("<b>Precio Unitario</b>", bold_p),
                Paragraph("<b>Descuento</b>", bold_p),
                Paragraph("<b>Precio Total</b>", bold_p)
            ]
        ]
        
        # Populate lines from XML or DB fallbacks
        if xml_data.get("detalles"):
            for d in xml_data["detalles"]:
                items_rows.append([
                    Paragraph(d["codigoPrincipal"], normal_p),
                    Paragraph(f"{float(d['cantidad']):.2f}", normal_p),
                    Paragraph(d["descripcion"], normal_p),
                    Paragraph(_fmt_money(d["precioUnitario"]), normal_p),
                    Paragraph(_fmt_money(d["descuento"]), normal_p),
                    Paragraph(_fmt_money(d["precioTotalSinImpuesto"]), normal_p)
                ])
        else:
            # Fallback to DTO items
            for d in (getattr(invoice, "items", None) or []):
                prod_code = f"PROD{d.product_id:03d}" if d.product_id else "PROD000"
                qty = float(d.quantity or 0)
                price = float(d.unit_price_snapshot or 0)
                items_rows.append([
                    Paragraph(prod_code, normal_p),
                    Paragraph(f"{qty:.2f}", normal_p),
                    Paragraph(d.product_name or "-", normal_p),
                    Paragraph(_fmt_money(price), normal_p),
                    Paragraph(_fmt_money(0.00), normal_p),
                    Paragraph(_fmt_money(price * qty), normal_p)
                ])
                
        items_table = Table(
            items_rows,
            colWidths=[28 * mm, 18 * mm, 78 * mm, 22 * mm, 20 * mm, 24 * mm],
            repeatRows=1
        )
        items_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("ALIGN", (1, 0), (1, -1), "CENTER"), # quantity
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"), # prices
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 4 * mm))

        # 6. Bottom section (Payments vs Totals)
        # Left Box (Payments table)
        payments_rows = [
            [Paragraph("<b>Forma de Pago</b>", bold_p), Paragraph("<b>Valor</b>", bold_p)]
        ]
        if xml_data.get("payments"):
            for p in xml_data["payments"]:
                lbl = "SIN UTILIZACION DEL SISTEMA FINANCIERO" if p["formaPago"] == "01" else f"OTRO ({p['formaPago']})"
                payments_rows.append([Paragraph(lbl, small_p), Paragraph(_fmt_money(p["total"]), small_p)])
        else:
            payments_rows.append([
                Paragraph("SIN UTILIZACION DEL SISTEMA FINANCIERO", small_p),
                Paragraph(_fmt_money(invoice.total_snapshot), small_p)
            ])
            
        payments_table = Table(payments_rows, colWidths=[70 * mm, 24 * mm])
        payments_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        
        payments_container = [
            Paragraph("<b>INFORMACIÓN DE PAGO</b>", bold_p),
            Spacer(1, 1.5 * mm),
            payments_table
        ]
        
        # Right Box (Totals Breakdown)
        subtotal = float(invoice.subtotal_snapshot or 0)
        tax_total = float(invoice.tax_total_snapshot or 0)
        total = float(invoice.total_snapshot or 0)
        
        # Prepare totals rows, detailing bases for SRI
        totals_breakdown = []
        
        if xml_data.get("tax_groups"):
            sub_0 = 0.0
            sub_15 = 0.0
            iva_15 = 0.0
            for tg in xml_data["tax_groups"]:
                tarifa = float(tg["tarifa"])
                base = float(tg["baseImponible"])
                val = float(tg["valor"])
                if tarifa == 0.0:
                    sub_0 += base
                else:
                    sub_15 += base
                    iva_15 += val
            totals_breakdown.extend([
                [Paragraph("SUBTOTAL 15%", small_p), Paragraph(_fmt_money(sub_15), small_p)],
                [Paragraph("SUBTOTAL 0%", small_p), Paragraph(_fmt_money(sub_0), small_p)],
                [Paragraph("SUBTOTAL SIN IMPUESTOS", small_p), Paragraph(_fmt_money(sub_15 + sub_0), small_p)],
                [Paragraph("TOTAL DESCUENTO", small_p), Paragraph(_fmt_money(0.00), small_p)],
                [Paragraph("IVA 15%", small_p), Paragraph(_fmt_money(iva_15), small_p)],
                [Paragraph("<b>VALOR TOTAL</b>", bold_p), Paragraph(f"<b>{_fmt_money(total)}</b>", bold_p)]
            ])
        else:
            # Fallback based on DTO items taxes
            has_tax = False
            for d in (getattr(invoice, "items", None) or []):
                if getattr(d, "taxes", None):
                    has_tax = True
                    break
            
            sub_15 = subtotal if has_tax else 0.0
            sub_0 = 0.0 if has_tax else subtotal
            iva_val = tax_total
            
            totals_breakdown.extend([
                [Paragraph("SUBTOTAL 15%", small_p), Paragraph(_fmt_money(sub_15), small_p)],
                [Paragraph("SUBTOTAL 0%", small_p), Paragraph(_fmt_money(sub_0), small_p)],
                [Paragraph("SUBTOTAL SIN IMPUESTOS", small_p), Paragraph(_fmt_money(subtotal), small_p)],
                [Paragraph("TOTAL DESCUENTO", small_p), Paragraph(_fmt_money(0.00), small_p)],
                [Paragraph("IVA 15%", small_p), Paragraph(_fmt_money(iva_val), small_p)],
                [Paragraph("<b>VALOR TOTAL</b>", bold_p), Paragraph(f"<b>{_fmt_money(total)}</b>", bold_p)]
            ])
            
        totals_table = Table(totals_breakdown, colWidths=[55 * mm, 31 * mm])
        totals_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        
        bottom_table = Table([[payments_container, totals_table]], colWidths=[98 * mm, 92 * mm])
        bottom_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        
        # Keep payments and totals together on page end
        story.append(KeepTogether([bottom_table]))

        if invoice.rejection_reason:
            story.append(Spacer(1, 4 * mm))
            story.append(
                Paragraph(
                    f"<b>Motivo de rechazo:</b> {invoice.rejection_reason}",
                    bold_p,
                )
            )

        doc.build(story)
        return buf.getvalue()
