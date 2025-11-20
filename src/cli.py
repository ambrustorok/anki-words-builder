import os
import uuid
from typing import Optional

import typer
from dotenv import load_dotenv

from .services import users as user_service
from .utils.admins import get_auto_admin_emails

load_dotenv()

app = typer.Typer(help="Administrative commands for Anki Words Builder.")
users_app = typer.Typer(help="User/profile management commands.")
app.add_typer(users_app, name="users")

LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "local@example.com")
PROTECTED_EMAILS = get_auto_admin_emails(LOCAL_USER_EMAIL)


def _require_profile(email: str) -> dict:
    normalized = (email or "").strip().lower()
    if not normalized:
        typer.secho("Provide an email address.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    profile = user_service.get_user_by_email(normalized)
    if not profile:
        typer.secho(f"No profile linked to {normalized}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return profile


def _find_email_entry(user_id: uuid.UUID, email: str) -> Optional[dict]:
    normalized = (email or "").strip().lower()
    for entry in user_service.list_user_emails(user_id):
        if entry["email"].lower() == normalized:
            return entry
    return None


@users_app.command("list")
def list_profiles(admins_only: bool = typer.Option(False, "--admins-only", help="Show only admin profiles.")):
    """Print a concise overview of all profiles."""
    rows = user_service.list_all_users()
    if admins_only:
        rows = [row for row in rows if row["is_admin"]]
    if not rows:
        typer.echo("No profiles found.")
        raise typer.Exit()
    header = f"{'Primary email':35} {'Native':12} {'Admin':5} {'Emails':6} ID"
    typer.echo(header)
    typer.echo("-" * len(header))
    for row in rows:
        typer.echo(
            f"{(row['primary_email'] or '—')[:35]:35} "
            f"{(row['native_language'] or '—')[:12]:12} "
            f"{'yes' if row['is_admin'] else 'no ':5} "
            f"{row['email_count']:>6} {row['id']}"
        )


@users_app.command("delete")
def delete_profile(email: str = typer.Argument(..., help="Any email linked to the profile.")):
    """Delete a profile (and all of its data)."""
    profile = _require_profile(email)
    primary_lower = (profile.get("primary_email") or "").lower()
    if primary_lower and primary_lower in PROTECTED_EMAILS:
        typer.secho("Cannot delete a protected admin profile.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not typer.confirm(f"Delete profile {profile['primary_email']}?"):
        typer.echo("Aborted.")
        raise typer.Exit()
    user_service.delete_user(profile["id"])
    typer.secho("Profile deleted.", fg=typer.colors.GREEN)


@users_app.command("update-email")
def update_email(
    current_email: str = typer.Argument(..., help="Existing email linked to the profile."),
    new_email: str = typer.Argument(..., help="Replacement email address."),
    make_primary: bool = typer.Option(False, "--set-primary/--keep-primary", help="Make the updated email the primary address."),
):
    """Rename an existing email address."""
    profile = _require_profile(current_email)
    entry = _find_email_entry(profile["id"], current_email)
    if not entry:
        typer.secho("That email is not linked to the profile.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    try:
        user_service.update_user_email(uuid.UUID(entry["id"]), new_email)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if make_primary:
        user_service.set_primary_email(profile["id"], uuid.UUID(entry["id"]))
    typer.secho("Email updated.", fg=typer.colors.GREEN)


@users_app.command("add-email")
def add_email(
    email: str = typer.Argument(..., help="Any email already linked to the target profile."),
    new_email: str = typer.Argument(..., help="Email to add to the profile."),
    make_primary: bool = typer.Option(False, "--set-primary/--keep-primary", help="Make the new email the primary address."),
):
    """Attach a new email address to an existing profile."""
    profile = _require_profile(email)
    try:
        user_service.add_user_email(profile["id"], new_email, make_primary=make_primary)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("Email added.", fg=typer.colors.GREEN)


@users_app.command("grant-admin")
def grant_admin(email: str = typer.Argument(..., help="Email linked to the profile.")):
    """Give the profile admin privileges."""
    profile = _require_profile(email)
    if profile.get("is_admin"):
        typer.echo("Profile is already an admin.")
        raise typer.Exit()
    user_service.set_admin_status(profile["id"], True)
    typer.secho("Admin access granted.", fg=typer.colors.GREEN)


@users_app.command("revoke-admin")
def revoke_admin(email: str = typer.Argument(..., help="Email linked to the profile.")):
    """Remove admin privileges."""
    profile = _require_profile(email)
    primary_lower = (profile.get("primary_email") or "").lower()
    if primary_lower and primary_lower in PROTECTED_EMAILS:
        typer.secho("Cannot revoke admin from a protected account.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not profile.get("is_admin"):
        typer.echo("Profile is not an admin.")
        raise typer.Exit()
    user_service.set_admin_status(profile["id"], False)
    typer.secho("Admin access revoked.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
