from __future__ import annotations

from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AscendTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#183227"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AscendHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#193F34"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AscendBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#17251F"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AscendSmall",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#51606F"),
            spaceAfter=6,
        )
    )
    return styles


def _clean(value: object) -> str:
    return str(value or "").strip()


def _paragraph(text: str, style_name: str, styles):
    return Paragraph((_clean(text) or "Not provided.").replace("\n", "<br/>"), styles[style_name])


def _section(story: list, heading: str, body: str, styles) -> None:
    story.append(Paragraph(heading, styles["AscendHeading"]))
    story.append(_paragraph(body, "AscendBody", styles))


def _heading(story: list, heading: str, styles) -> None:
    story.append(Paragraph(heading, styles["AscendHeading"]))


def _field_table(rows: Iterable[tuple[str, str]], styles):
    data = []
    for label, value in rows:
        data.append(
            [
                Paragraph(f"<b>{label}</b>", styles["AscendBody"]),
                Paragraph((_clean(value) or "Not provided.").replace("\n", "<br/>"), styles["AscendBody"]),
            ]
        )
    table = Table(data, colWidths=[150, 360], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DFD6C7")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DFD6C7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def render_critical_role_pdf(member_name: str, project: dict) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=36, bottomMargin=36)
    story: list = []

    story.append(Paragraph("Critical Role Questionnaire Export", styles["AscendTitle"]))
    story.append(_paragraph(f"Member: {member_name or 'Member not identified'}", "AscendBody", styles))
    story.append(_paragraph("Structured from the Ascend member portal using the critical role intake template format.", "AscendSmall", styles))
    story.append(Spacer(1, 6))

    story.append(
        _field_table(
            [
                ("Organization", _clean(project.get("organization_name"))),
                ("Business Unit / Team", _clean(project.get("organization_unit"))),
                ("Organization Location", _clean(project.get("organization_location"))),
                ("Employment Type", _clean(project.get("employment_type"))),
                ("Job Title / Role Title", _clean(project.get("role_title"))),
                ("Role Dates", _clean(project.get("role_date_label"))),
                ("Project", _clean(project.get("project_name"))),
                ("Project Dates", _clean(project.get("project_date_label"))),
                ("Project Status", _clean(project.get("project_status"))),
                ("Workflow Status", _clean(project.get("workflow_status")).title()),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 10))

    _section(story, "Part 1: Critical Role and Impact", project.get("role_summary", ""), styles)
    _section(story, "Role and Responsibilities", project.get("role_responsibilities", ""), styles)
    _section(story, "Evolution and Impact", project.get("role_evolution", ""), styles)
    _section(story, "Leadership in Key Projects", project.get("project_summary", ""), styles)
    _section(story, "Business Need or Problem", project.get("business_need", ""), styles)
    _section(story, "Strategic Importance", project.get("strategic_importance", ""), styles)
    _section(story, "Role / Contribution to the Project", project.get("contributions_summary", ""), styles)

    _heading(story, "Part 2: Organization's Distinguished Reputation", styles)
    _section(story, "Organization's Achievements", project.get("organization_achievements", ""), styles)
    _section(story, "Organization's Distinctiveness", project.get("organization_distinctiveness", ""), styles)

    _heading(story, "Part 3: Distinction from Peers", styles)
    _section(story, "Leadership and Expertise Beyond Title", project.get("peer_distinction_summary", ""), styles)
    _section(story, "Leadership Scope", project.get("leadership_scope", ""), styles)
    _section(story, "Cross-functional Partnerships", project.get("cross_functional_partners", ""), styles)
    _section(story, "Mentorship / Leadership Beyond Title", project.get("mentorship_leadership", ""), styles)
    _section(story, "Executive Visibility", project.get("executive_visibility", ""), styles)

    _heading(story, "Business Value and Metrics", styles)
    _section(story, "Business Value Summary", project.get("business_value_summary", ""), styles)
    _section(story, "Quantitative Metrics", project.get("quantitative_metrics", ""), styles)
    _section(story, "Revenue Impact", project.get("revenue_impact", ""), styles)
    _section(story, "Cost Savings", project.get("cost_savings", ""), styles)
    _section(story, "Efficiency Gain", project.get("efficiency_gain", ""), styles)
    _section(story, "User / Customer Impact", project.get("user_or_customer_impact", ""), styles)
    _section(story, "Market / Geographic Impact", project.get("market_or_geographic_impact", ""), styles)
    _section(story, "Compliance / Risk Impact", project.get("compliance_or_risk_impact", ""), styles)
    _section(story, "Originality / Innovation", project.get("innovation_originality", ""), styles)
    _section(story, "Evidence Available", project.get("evidence_available", ""), styles)
    _section(story, "Attorney-Friendly Summary", project.get("attorney_friendly_summary", ""), styles)

    doc.build(story)
    return buffer.getvalue()


def render_original_contribution_pdf(member_name: str, entry: dict) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=36, bottomMargin=36)
    story: list = []

    story.append(Paragraph("Original Contributions Questionnaire Export", styles["AscendTitle"]))
    story.append(_paragraph(f"Member: {member_name or 'Member not identified'}", "AscendBody", styles))
    story.append(_paragraph("Structured from the Ascend member portal using the original contributions intake template format.", "AscendSmall", styles))
    story.append(Spacer(1, 6))

    story.append(
        _field_table(
            [
                ("Contribution Title", _clean(entry.get("contribution_title"))),
                ("Contribution Category", _clean(entry.get("contribution_category"))),
                ("Field of Expertise", _clean(entry.get("field_of_expertise"))),
                ("Job Title", _clean(entry.get("job_title"))),
                ("Organization / Context", _clean(entry.get("organization_name"))),
                ("Project / Product", _clean(entry.get("project_name"))),
                ("Contribution Dates", _clean(entry.get("date_label"))),
                ("Contribution Status", _clean(entry.get("contribution_status"))),
                ("Workflow Status", _clean(entry.get("workflow_status")).title()),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 10))

    _heading(story, "Part 1: Originality and Innovation", styles)
    _section(story, "Innovative Contribution", entry.get("originality_summary", ""), styles)
    _section(story, "Challenging Paradigms", entry.get("challenging_paradigms", ""), styles)
    _section(story, "Prior State of the Field", entry.get("prior_state_of_field", ""), styles)
    _section(story, "Solution or Innovation", entry.get("solution_or_innovation", ""), styles)
    _section(story, "Unique Features / Use Cases", entry.get("unique_features", ""), styles)

    _heading(story, "Part 2: Work-Related vs. External Contributions", styles)
    _section(story, "Context of the Contribution", entry.get("work_vs_external_context", ""), styles)
    _section(story, "Personal Role", entry.get("personal_role", ""), styles)
    _section(story, "Distinct Contribution", entry.get("distinct_contribution_summary", ""), styles)
    _section(story, "Technical or Business Problem", entry.get("technical_or_business_problem", ""), styles)

    _heading(story, "Part 3: Major Significance and Impact", styles)
    _section(story, "Impact Metrics", entry.get("impact_metrics", ""), styles)
    _section(story, "Adoption Scale", entry.get("adoption_scale", ""), styles)
    _section(story, "Beneficiaries", entry.get("beneficiary_summary", ""), styles)
    _section(story, "Time Savings", entry.get("time_savings", ""), styles)
    _section(story, "Cost Savings", entry.get("cost_savings", ""), styles)
    _section(story, "Revenue / Funding Impact", entry.get("revenue_impact", ""), styles)
    _section(story, "Quality / Risk Impact", entry.get("quality_or_risk_impact", ""), styles)
    _section(story, "Broader Field Impact", entry.get("field_wide_impact", ""), styles)
    _section(story, "Recognition and Influence", entry.get("recognition_and_influence", ""), styles)
    _section(story, "Media or Public Mentions", entry.get("media_or_public_mentions", ""), styles)
    _section(story, "Adoption Letters / Reference Targets", entry.get("adoption_letters_targets", ""), styles)
    _section(story, "Evidence Available", entry.get("evidence_available", ""), styles)
    _section(story, "Attorney-Friendly Summary", entry.get("attorney_friendly_summary", ""), styles)

    doc.build(story)
    return buffer.getvalue()
