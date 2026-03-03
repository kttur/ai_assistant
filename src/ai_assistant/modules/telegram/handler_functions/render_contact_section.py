from __future__ import annotations


def render_contact_section(contact) -> str:
    lines = ["Contact in message:"]
    contact_user_id = getattr(contact, "user_id", None)
    if contact_user_id is None:
        lines.append("ID: (not linked)")
    else:
        lines.append(f"ID: {contact_user_id}")
    first_name = getattr(contact, "first_name", None)
    last_name = getattr(contact, "last_name", None)
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    if full_name:
        lines.append(f"Name: {full_name}")
    phone = getattr(contact, "phone_number", None)
    if phone:
        lines.append(f"Phone: {phone}")
    return "\n".join(lines)
