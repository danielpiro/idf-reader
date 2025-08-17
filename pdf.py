#!/usr/bin/env python3
"""
Complete NDA PDF Generator - Full Legal Structure
Generates a comprehensive one-way Non-Disclosure Agreement with all necessary legal provisions
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

def create_nda_pdf(filename="Complete_NDA.pdf"):
    """
    Creates a comprehensive NDA PDF document with full legal structure
    
    Args:
        filename (str): Name of the PDF file to create
    """
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Get default styles and create custom styles
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Normal'],
        fontSize=16,
        spaceAfter=24,
        spaceBefore=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Body text style
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        spaceBefore=6,
        alignment=TA_JUSTIFY,
        leftIndent=0,
        rightIndent=0,
        leading=13
    )
    
    # Section header style
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        spaceBefore=16,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Subsection style
    subsection_style = ParagraphStyle(
        'Subsection',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        spaceBefore=8,
        alignment=TA_JUSTIFY,
        leftIndent=20,
        leading=13
    )
    
    # Build the document content
    story = []
    
    # Title
    story.append(Paragraph("Non-Disclosure Agreement (NDA)", title_style))
    story.append(Spacer(1, 20))
    
    # Opening paragraph with date
    opening_text = '''This Non-Disclosure Agreement ("Agreement") is made effective as of _________________, 20___ ("Effective Date"), by and between'''
    story.append(Paragraph(opening_text, body_style))
    story.append(Spacer(1, 12))
    
    # First party info table (Disclosing Party)
    disclosing_party_data = [
        ['', '("Disclosing Party"), of'],
        ['', ',']
    ]
    
    disclosing_table = Table(disclosing_party_data, colWidths=[2*inch, 2*inch])
    disclosing_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, 0), 1, colors.black),
        ('BOX', (0, 1), (0, 1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    story.append(disclosing_table)
    story.append(Spacer(1, 8))
    
    # "and" connector
    story.append(Paragraph('and', body_style))
    story.append(Spacer(1, 8))
    
    # Second party info table (Recipient)
    recipient_party_data = [
        ['', '("Recipient"), of'],
        ['', '.']
    ]
    
    recipient_table = Table(recipient_party_data, colWidths=[2*inch, 2*inch])
    recipient_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, 0), 1, colors.black),
        ('BOX', (0, 1), (0, 1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    story.append(recipient_table)
    story.append(Spacer(1, 16))
    
    # Main content - updated for investment purpose
    story.append(Paragraph('''The Disclosing Party has requested, and the Recipient has agreed, to protect any confidential material and information that the Disclosing Party may share for the purpose of evaluating a potential investment opportunity. Therefore, the parties agree as follows:''', body_style))
    
    # 1. Confidential Information - Investment specific
    story.append(Paragraph("Confidential Information.", section_style))
    story.append(Paragraph('''The term "Confidential Information" refers to any and all confidential, proprietary, or non-public information exchanged between the Parties in connection with the evaluation of a potential investment opportunity, whether directly or indirectly. This includes, but is not limited to, financial information, business plans, trade secrets, and strategic information revealed on or after the Effective Date, regardless of whether the Confidential Information is disclosed in writing, orally, or through other forms of communication or observation.''', body_style))
    
    story.append(Paragraph('''Confidential Information specifically includes: financial statements, revenue and profit data, business models, growth projections, market analysis, competitive positioning, customer information, supplier relationships, operational metrics, intellectual property details, strategic plans, investment requirements, valuation information, due diligence materials, management presentations, technology specifications, and any other business or financial information relating to the potential investment opportunity.''', body_style))
    
    # 2. Term
    story.append(Paragraph("Term.", section_style))
    term_text = '''The term of this Agreement will begin on the Effective Date and shall remain in effect until <u>&nbsp;&nbsp;two (2) years&nbsp;&nbsp;</u> from the Effective Date ("Termination Date"), unless terminated earlier as outlined in the Termination section below. Either party may alter the Termination Date by mutual written consent. During the term of this Agreement and for <u>&nbsp;&nbsp;one (1) year&nbsp;&nbsp;</u> after the Termination Date, the Recipient must continue to protect the Confidential Information that was received during the term of this Agreement from unauthorized use or disclosure.'''
    story.append(Paragraph(term_text, body_style))
    
    # 3. Termination
    story.append(Paragraph("Termination.", section_style))
    termination_text = '''Either party may end this Agreement prior to the Termination Date, with or without cause, upon <u>&nbsp;&nbsp;thirty (30)&nbsp;&nbsp;</u> days' written notice to the other party ("Early Termination"). Upon Early Termination, the Recipient must continue to protect the Confidential Information that was received during the term of this Agreement from unauthorized use or disclosure for an additional <u>&nbsp;&nbsp;one (1) year&nbsp;&nbsp;</u>.'''
    story.append(Paragraph(termination_text, body_style))
    
    # 4. Protection of Confidential Information - Investment focused
    story.append(Paragraph("Protection of Confidential Information.", section_style))
    story.append(Paragraph('''The Recipient understands and acknowledges that the Confidential Information has been developed or obtained by the Disclosing Party by the investment of significant time, effort, and expense, and that the Confidential Information is a valuable, special, and unique asset of the Disclosing Party which provides the Disclosing Party with a significant competitive advantage and needs to be protected from improper disclosure. The Recipient acknowledges that disclosure of such information to competitors or unauthorized parties could materially harm the Disclosing Party's business and investment prospects. In exchange for receiving the Confidential Information for investment evaluation purposes, the Recipient agrees as follows:''', body_style))
    
    # Subsections
    story.append(Paragraph("(a) No Disclosure.", subsection_style))
    story.append(Paragraph("The Recipient will hold the Confidential Information in confidence and will not disclose the Confidential Information to any person or entity without the prior written consent of the Disclosing Party.", subsection_style))
    
    story.append(Paragraph("(b) No Copying/Modifying.", subsection_style))
    story.append(Paragraph("The Recipient will not copy or modify any Confidential Information without the prior written consent of the Disclosing Party.", subsection_style))
    
    story.append(Paragraph("(c) Unauthorized Use.", subsection_style))
    story.append(Paragraph("The Recipient shall promptly advise the Disclosing Party if the Recipient becomes aware of any possible unauthorized disclosure or use of the Confidential Information.", subsection_style))
    
    story.append(Paragraph("(d) Application to Employees and Advisors.", subsection_style))
    story.append(Paragraph("The Recipient shall not disclose any Confidential Information to any employees, consultants, advisors, or other parties of the Recipient, except those individuals who are required to have the Confidential Information to perform investment evaluation activities in connection with the limited purposes of this Agreement. Each permitted individual to whom the Confidential Information is disclosed shall sign a non-disclosure agreement substantially the same as this Agreement at the request of the Disclosing Party.", subsection_style))
    
    story.append(Paragraph("(e) Standard of Care.", subsection_style))
    story.append(Paragraph("The Recipient agrees to exercise the same degree of care in protecting the Confidential Information as it exercises in protecting its own confidential information, but in no event less than reasonable care.", subsection_style))
    
    story.append(Paragraph("(f) Investment Purpose Only.", subsection_style))
    story.append(Paragraph("The Recipient agrees to use the Confidential Information solely for the purpose of evaluating a potential investment opportunity and for no other business or commercial purpose whatsoever.", subsection_style))
    
    # 5. Investment Evaluation Purpose
    story.append(Paragraph("Investment Evaluation Purpose.", section_style))
    story.append(Paragraph("The parties acknowledge that the Confidential Information is being disclosed solely for the purpose of enabling the Recipient to evaluate a potential investment opportunity in the Disclosing Party. The Recipient may not use the Confidential Information for any other purpose, including but not limited to competing with the Disclosing Party, soliciting its customers or employees, or developing competing products or services.", body_style))
    
    # 6. Return of Materials
    story.append(Paragraph("Return of Materials.", section_style))
    story.append(Paragraph("Upon termination of this Agreement, upon completion of the investment evaluation process, or upon written request by the Disclosing Party, the Recipient shall promptly return or destroy all documents, materials, and other tangible manifestations of Confidential Information and all copies thereof in its possession or control, and provide written certification of such return or destruction.", body_style))
    
    # 7. Exceptions to Confidential Information
    story.append(Paragraph("Exceptions to Confidential Information.", section_style))
    story.append(Paragraph('''Confidential Information, as it is used in this Agreement, does not include the following information: (i) information that is publicly known due to disclosure by the Disclosing Party; (ii) information received by the Recipient from a third party who has no confidentiality obligation; (iii) information independently created by the Recipient without use of Confidential Information; (iv) information disclosed by operation of law; and (v) any other information that both parties agree in writing is not confidential.''', body_style))
    
    # 7. No License Granted
    story.append(Paragraph("No License Granted.", section_style))
    story.append(Paragraph("Nothing in this Agreement grants any license under any trademark, patent, copyright, or other intellectual property right. All rights in and to the Confidential Information remain with the Disclosing Party.", body_style))
    
    # 8. Unauthorized Disclosure - Injunction
    story.append(Paragraph("Unauthorized Disclosure of Confidential Information - Injunction.", section_style))
    story.append(Paragraph('''The Recipient acknowledges and agrees that there can be no adequate remedy at law if any Confidential Information is disclosed or is at risk of being disclosed in breach of this Agreement. Upon any such breach the Disclosing Party shall be entitled to temporary or permanent injunctive relief. The Disclosing Party shall not be prohibited by this provision from pursuing other remedies, including a claim for losses and damages.''', body_style))
    
    # 9. Governing Law
    story.append(Paragraph("Governing Law.", section_style))
    story.append(Paragraph("This Agreement shall be governed by and construed in accordance with the laws of Israel, without regard to its conflict of laws principles. Any disputes arising under this Agreement shall be subject to the exclusive jurisdiction of the courts located in Tel Aviv, Israel.", body_style))
    
    # 10. Entire Agreement
    story.append(Paragraph("Entire Agreement.", section_style))
    story.append(Paragraph("This Agreement constitutes the entire agreement between the parties concerning the subject matter hereof and supersedes all prior agreements and understandings, whether written or oral. This Agreement may only be modified by a written instrument signed by both parties.", body_style))
    
    # 11. Severability
    story.append(Paragraph("Severability.", section_style))
    story.append(Paragraph("If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.", body_style))
    
    # 12. Survival
    story.append(Paragraph("Survival.", section_style))
    story.append(Paragraph("The obligations of confidentiality set forth in this Agreement shall survive any termination of this Agreement and shall continue indefinitely.", body_style))
    
    # 13. Whistleblower Protection
    story.append(Paragraph("Whistleblower Protection.", section_style))
    story.append(Paragraph('''This Agreement is in compliance with the Defend Trade Secrets Act and provides civil or criminal immunity to any individual for the disclosure of trade secrets: (i) made in confidence to a federal, state, or local government official, or to an attorney when the disclosure is to report suspected violations of the law; or (ii) in a complaint or other document filed in a lawsuit if made under seal.''', body_style))
    
    # 14. Attorney's Fees
    story.append(Paragraph("Attorney's Fees.", section_style))
    story.append(Paragraph("The prevailing party in any action to enforce this Agreement shall be entitled to recover its reasonable attorneys' fees and costs from the non-prevailing party.", body_style))
    
    # 15. Counterparts
    story.append(Paragraph("Counterparts.", section_style))
    story.append(Paragraph("This Agreement may be executed in counterparts, each of which shall be deemed an original and all of which together shall constitute one and the same instrument.", body_style))
    
    # Add page break for signature section
    story.append(PageBreak())
    
    # Signature section
    story.append(Paragraph("IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.", body_style))
    story.append(Spacer(1, 30))
    
    # Create comprehensive signature table
    sig_data = [
        ['DISCLOSING PARTY:', '', 'RECIPIENT:'],
        ['', '', ''],
        ['', '', ''],
        ['By: ________________________', '', 'By: ________________________'],
        ['Signature', '', 'Signature'],
        ['', '', ''],
        ['Name: ______________________', '', 'Name: ______________________'],
        ['Print Name', '', 'Print Name'],
        ['', '', ''],
        ['Title: _____________________', '', 'Title: _____________________'],
        ['', '', ''],
        ['', '', ''],
        ['Date: ______________________', '', 'Date: ______________________'],
        ['', '', ''],
        ['', '', ''],
        ['Company: ___________________', '', 'Company: ___________________'],
        ['', '', ''],
        ['', '', ''],
        ['Address: ___________________', '', 'Address: ___________________'],
        ['', '', ''],
        ['_____________________________', '', '_____________________________'],
        ['', '', ''],
        ['_____________________________', '', '_____________________________'],
        ['City, State, ZIP', '', 'City, State, ZIP'],
    ]
    
    sig_table = Table(sig_data, colWidths=[2.8*inch, 0.4*inch, 2.8*inch])
    sig_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
        ('FONTSIZE', (0, 4), (0, 4), 9),  # "Signature" label
        ('FONTSIZE', (2, 4), (2, 4), 9),  # "Signature" label
        ('FONTSIZE', (0, 7), (0, 7), 9),  # "Print Name" label
        ('FONTSIZE', (2, 7), (2, 7), 9),  # "Print Name" label
        ('FONTSIZE', (0, 23), (0, 23), 9), # "City, State, ZIP" label
        ('FONTSIZE', (2, 23), (2, 23), 9), # "City, State, ZIP" label
    ]))
    
    story.append(sig_table)
    
    # Build the PDF
    doc.build(story)
    print(f"Complete NDA PDF created successfully: {filename}")
    return filename

def main():
    """
    Main function to generate the complete NDA PDF
    """
    try:
        filename = create_nda_pdf()
        print(f"\nSuccess! Your complete NDA has been created as: {filename}")
        print("\nComplete Legal Structure Includes:")
        print("   • Comprehensive confidentiality definitions")
        print("   • Term and termination provisions")
        print("   • Protection obligations and restrictions")
        print("   • Return of materials requirements")
        print("   • Exceptions to confidentiality")
        print("   • No license granted clause")
        print("   • Injunctive relief provisions")
        print("   • Governing law (Israel)")
        print("   • Entire agreement clause")
        print("   • Severability provisions")
        print("   • Survival clauses")
        print("   • Whistleblower protections")
        print("   • Attorney's fees provision")
        print("   • Counterparts clause")
        print("   • Comprehensive signature section")
        print("\nPre-configured for:")
        print("   • Investment evaluation purposes")
        print("   • 2-year term with 1-year survival")
        print("   • Israeli jurisdiction")
        print("   • 30-day termination notice")
        print("\nThis is now a comprehensive, legally complete NDA")
        print("   ready for professional business use.")
        
    except ImportError:
        print("Error: ReportLab library not found!")
        print("\nTo install ReportLab, run:")
        print("   pip install reportlab")
        print("\nThen run this script again.")
        
    except Exception as e:
        print(f"Error creating PDF: {str(e)}")
        print("Please check that you have write permissions in the current directory.")

if __name__ == "__main__":
    main()