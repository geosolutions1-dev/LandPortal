# payment_slip.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from datetime import datetime
import os
import qrcode
from io import BytesIO
import base64

# Try to import barcode, fallback to text if not available
try:
    from reportlab.graphics.barcode import code128

    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("Barcode module not available, using text instead")


def generate_payment_slip(application, payment, user):
    """
    Generate a PDF payment slip for the application with QR code
    Suitable for A5 printing
    """
    # Create filename
    filename = f"payment_slip_{application['application_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join('static/uploads/payments', filename)

    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Use A5 size for easier printing
    page_size = A5
    doc = SimpleDocTemplate(filepath, pagesize=page_size,
                            topMargin=0.4 * inch, bottomMargin=0.4 * inch,
                            leftMargin=0.3 * inch, rightMargin=0.3 * inch)

    # Service names mapping for full display
    service_names = {
        'land_transfer': 'Land Transfer',
        'surveying_mapping': 'Surveying & Mapping',
        'boundaries': 'Boundary Demarcation',
        'land_search': 'Land Search',
        'title_deed': 'Title Deed Processing',
        'land_valuation': 'Land Valuation',
        'lease_registration': 'Lease Registration',
        'topographic_surveying': 'Topographic Surveying',
        'building_plan_approval': 'Building Plan Approval',
        'land_consolidation': 'Land Consolidation',
        'land_subdivision': 'Land Subdivision',
        'change_of_user': 'Change of User'
    }

    # Styles - Reduced font sizes for A5
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=12,
        textColor=colors.HexColor('#1e40af'),
        alignment=1,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=8,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6,
        alignment=1
    )

    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading4'],
        fontSize=8,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=7,
        spaceAfter=2,
        leading=9
    )

    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=6,
        spaceAfter=1,
        textColor=colors.HexColor('#64748b')
    )

    # Generate QR Code with application number and receipt number only
    qr_data = f"App: {application['application_number']} | Receipt: RCP-{payment['transaction_id']}"

    # Create QR code image
    qr_img = qrcode.make(qr_data)
    qr_img = qr_img.resize((80, 80))

    # Save QR code to BytesIO
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    # Create ReportLab Image from QR code
    qr_drawing = Image(qr_buffer, width=0.9 * inch, height=0.9 * inch)

    # Story (content) list
    story = []

    # Header
    story.append(Paragraph("LAND SERVICES PORTAL", title_style))
    story.append(Paragraph("Authentic Portal for Your Land Services", header_style))
    story.append(Spacer(1, 0.05 * inch))

    # Title
    story.append(Paragraph("PAYMENT RECEIPT", heading_style))
    story.append(Spacer(1, 0.05 * inch))

    # Receipt info with QR code side by side
    receipt_data = [
        ["Receipt No:", f"RCP-{payment['transaction_id']}"],
        ["Date Issued:", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Status:", "COMPLETED"],
    ]

    receipt_table = Table(receipt_data, colWidths=[0.9 * inch, 2.5 * inch])
    receipt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1e293b')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # Combine receipt table and QR code
    combined_data = [[receipt_table, qr_drawing]]
    combined_table = Table(combined_data, colWidths=[3.4 * inch, 0.9 * inch])
    combined_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(combined_table)
    story.append(Spacer(1, 0.08 * inch))

    # Customer Information
    story.append(Paragraph("CUSTOMER", heading_style))
    story.append(Spacer(1, 0.03 * inch))

    customer_info = [
        ["Name:", user['full_name']],
        ["ID:", user['national_id']],
        ["Email:", user['email']],
        ["Phone:", user['phone']],
    ]

    customer_table = Table(customer_info, colWidths=[0.7 * inch, 3.5 * inch])
    customer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1e293b')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(customer_table)
    story.append(Spacer(1, 0.06 * inch))

    # Payment Details
    story.append(Paragraph("PAYMENT", heading_style))
    story.append(Spacer(1, 0.03 * inch))

    payment_details = [
        ["App No:", application['application_number']],
        ["Service:",
         service_names.get(application['service_type'], application['service_type'].replace('_', ' ').title())],
        ["Location:", application['property_location']],
        ["Amount:", f"GHC {payment['amount']:,.2f}"],
        ["Method:", payment['payment_method'].upper()],
        ["Txn ID:", payment['transaction_id']],
        ["Paid On:", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]

    payment_table = Table(payment_details, colWidths=[0.7 * inch, 3.5 * inch])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1e293b')),
        ('BACKGROUND', (1, 3), (1, 3), colors.HexColor('#d1fae5')),
        ('TEXTCOLOR', (1, 3), (1, 3), colors.HexColor('#065f46')),
        ('FONTNAME', (1, 3), (1, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 3), (1, 3), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 0.06 * inch))

    # Receipt Barcode
    story.append(Paragraph("RECEIPT ID", heading_style))
    story.append(Spacer(1, 0.03 * inch))

    receipt_number = f"RCP-{payment['transaction_id']}"

    if BARCODE_AVAILABLE:
        try:
            barcode = code128.Code128(receipt_number, barHeight=0.3 * inch, barWidth=0.018 * inch)
            barcode.hAlign = 'CENTER'
            story.append(barcode)
        except:
            story.append(Paragraph(f"<b>{receipt_number}</b>", normal_style))
    else:
        barcode_text = "=" * 35
        story.append(Paragraph(barcode_text, normal_style))
        story.append(Paragraph(f"<b>{receipt_number}</b>", normal_style))
        story.append(Paragraph(barcode_text, normal_style))

    story.append(Spacer(1, 0.06 * inch))

    # Terms
    terms = [
        "• System generated receipt - No signature required",
        "• Payment confirms your application",
        "• Retain this receipt for reference",
    ]

    for term in terms:
        story.append(Paragraph(term, small_style))

    story.append(Spacer(1, 0.05 * inch))

    # Footer
    footer_text = """
    <font size=5 color='#64748b'>
    <hr/>
    <b>Land Services Portal</b> | Accra, Ghana<br/>
    Tel: +233 (0) 501500034 | Email: info@landadmin.gov.gh<br/>
    Scan QR code to verify
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))

    # Build PDF
    doc.build(story)
    relative_path = f"static/uploads/payments/{filename}"
    return relative_path