"""
License Dialog for IDF Reader
Handles license activation, trial management, and license status display.
"""

import flet as ft
from typing import Callable, Optional
from utils.license_manager import license_manager, LicenseManager
from utils.logging_config import get_logger

logger = get_logger(__name__)

class LicenseDialog:
    """License management dialog for the application."""
    
    def __init__(self, page: ft.Page, on_license_changed: Optional[Callable] = None):
        self.page = page
        self.on_license_changed = on_license_changed
        self.dialog = None
        
        # UI Components
        self.serial_key_field = None
        self.status_text = None
        self.feature_list = None
        self.activate_button = None
        self.deactivate_button = None
        
    def show_license_dialog(self, show_activation: bool = True):
        """Show the license management dialog."""
        try:
            self.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("ניהול רישיון", size=24, weight=ft.FontWeight.BOLD),
                content=self._create_dialog_content(show_activation),
                actions=[
                    ft.TextButton("סגור", on_click=self._close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            self.page.dialog = self.dialog
            self.dialog.open = True
            self.page.update()
            
            # Update status
            self._update_license_status()
            
        except Exception as e:
            logger.error(f"Error showing license dialog: {e}")
            self._show_error("שגיאה בהצגת חלון הרישיון")
    
    def _create_dialog_content(self, show_activation: bool) -> ft.Container:
        """Create the main content of the license dialog."""
        
        # Current status section
        self.status_text = ft.Text(
            "בודק סטטוס רישיון...",
            size=16,
            color=ft.colors.BLUE_600
        )
        
        status_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("סטטוס רישיון נוכחי", size=18, weight=ft.FontWeight.BOLD),
                    self.status_text,
                    ft.Divider(),
                    ft.Text("תכונות זמינות:", size=14, weight=ft.FontWeight.W_500),
                    self._create_feature_list()
                ]),
                padding=15
            ),
            elevation=2
        )
        
        content_items = [status_card]
        
        # Activation section (if needed)
        if show_activation:
            activation_card = self._create_activation_section()
            content_items.append(activation_card)
        
        # Machine ID section
        machine_id_card = self._create_machine_id_section()
        content_items.append(machine_id_card)
        
        return ft.Container(
            content=ft.Column(
                content_items,
                spacing=15,
                tight=True
            ),
            width=500,
            height=600,
        )
    
    def _create_activation_section(self) -> ft.Card:
        """Create the license activation section."""
        
        self.serial_key_field = ft.TextField(
            label="מפתח רישיון",
            hint_text="XXXX-XXXX-XXXX-XXXX",
            max_length=19,  # Including dashes
            text_align=ft.TextAlign.CENTER,
            on_change=self._format_serial_key
        )
        
        self.activate_button = ft.ElevatedButton(
            text="הפעל רישיון",
            icon=ft.icons.VPN_KEY,
            on_click=self._activate_license,
            style=ft.ButtonStyle(
                bgcolor=ft.colors.GREEN_600,
                color=ft.colors.WHITE
            )
        )
        
        self.deactivate_button = ft.ElevatedButton(
            text="בטל רישיון",
            icon=ft.icons.CANCEL,
            on_click=self._deactivate_license,
            style=ft.ButtonStyle(
                bgcolor=ft.colors.RED_600,
                color=ft.colors.WHITE
            )
        )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("הפעלת רישיון", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "הזן מפתח רישיון לקבלת גישה מלאה לכל התכונות",
                        size=14,
                        color=ft.colors.GREY_600
                    ),
                    self.serial_key_field,
                    ft.Row([
                        self.activate_button,
                        self.deactivate_button
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ]),
                padding=15
            ),
            elevation=2
        )
    
    def _create_machine_id_section(self) -> ft.Card:
        """Create the machine ID section."""
        
        machine_id = license_manager.get_machine_id()
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("מזהה מחשב", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "מזהה זה נדרש להפעלת הרישיון",
                        size=14,
                        color=ft.colors.GREY_600
                    ),
                    ft.TextField(
                        value=machine_id,
                        read_only=True,
                        text_align=ft.TextAlign.CENTER,
                        border_color=ft.colors.GREY_400
                    ),
                    ft.ElevatedButton(
                        text="העתק למשטח",
                        icon=ft.icons.COPY,
                        on_click=lambda _: self._copy_to_clipboard(machine_id),
                        style=ft.ButtonStyle(
                            bgcolor=ft.colors.BLUE_600,
                            color=ft.colors.WHITE
                        )
                    )
                ]),
                padding=15
            ),
            elevation=2
        )
    
    def _create_feature_list(self) -> ft.Container:
        """Create the feature list display."""
        
        self.feature_list = ft.Column(
            spacing=5,
            tight=True
        )
        
        return ft.Container(
            content=self.feature_list,
            height=150,
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=8,
            padding=10
        )
    
    def _format_serial_key(self, e):
        """Format serial key input with dashes."""
        try:
            # Remove all non-alphanumeric characters
            clean_key = ''.join(c for c in e.control.value.upper() if c.isalnum())
            
            # Add dashes every 4 characters
            formatted = ''
            for i, char in enumerate(clean_key):
                if i > 0 and i % 4 == 0:
                    formatted += '-'
                formatted += char
            
            # Limit to 16 characters (plus dashes)
            if len(clean_key) > 16:
                formatted = formatted[:19]  # 16 chars + 3 dashes
            
            e.control.value = formatted
            e.control.update()
            
        except Exception as ex:
            logger.error(f"Error formatting serial key: {ex}")
    
    def _activate_license(self, e):
        """Activate license with entered serial key."""
        try:
            if not self.serial_key_field or not self.serial_key_field.value:
                self._show_error("אנא הזן מפתח רישיון")
                return
            
            serial_key = self.serial_key_field.value.strip()
            
            # Show loading
            self.activate_button.text = "מפעיל..."
            self.activate_button.disabled = True
            self.page.update()
            
            # Activate license
            success, message = license_manager.activate_license(serial_key)
            
            if success:
                self._show_success(message)
                self._update_license_status()
                if self.on_license_changed:
                    self.on_license_changed()
            else:
                self._show_error(message)
            
        except Exception as ex:
            logger.error(f"License activation error: {ex}")
            self._show_error(f"שגיאה בהפעלת הרישיון: {ex}")
        
        finally:
            # Reset button
            self.activate_button.text = "הפעל רישיון"
            self.activate_button.disabled = False
            self.page.update()
    
    def _deactivate_license(self, e):
        """Deactivate current license."""
        try:
            # Confirm deactivation
            def confirm_deactivate(e):
                if license_manager.deactivate_license():
                    self._show_success("הרישיון בוטל בהצלחה")
                    self._update_license_status()
                    if self.on_license_changed:
                        self.on_license_changed()
                else:
                    self._show_error("שגיאה בביטול הרישיון")
                confirm_dialog.open = False
                self.page.update()
            
            confirm_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("אישור ביטול רישיון"),
                content=ft.Text("האם אתה בטוח שברצונך לבטל את הרישיון?\nהתוכנה תעבור למצב מוגבל."),
                actions=[
                    ft.TextButton("בטל", on_click=lambda _: setattr(confirm_dialog, 'open', False) or self.page.update()),
                    ft.TextButton("אשר ביטול", on_click=confirm_deactivate),
                ],
            )
            
            self.page.dialog = confirm_dialog
            confirm_dialog.open = True
            self.page.update()
            
        except Exception as ex:
            logger.error(f"License deactivation error: {ex}")
            self._show_error(f"שגיאה בביטול הרישיון: {ex}")
    
    def _update_license_status(self):
        """Update the license status display."""
        try:
            status = license_manager.get_license_status()
            
            # Update status text
            if status["status"] == LicenseManager.STATUS_VALID:
                license_type = status.get("type", "לא ידוע")
                expires = status.get("expires")
                
                if expires:
                    from datetime import datetime
                    exp_date = datetime.fromisoformat(expires)
                    expires_text = exp_date.strftime("%d/%m/%Y")
                    status_text = f"רישיון פעיל: {license_type}\nתוקף עד: {expires_text}"
                else:
                    status_text = f"רישיון פעיל: {license_type}"
                
                self.status_text.value = status_text
                self.status_text.color = ft.colors.GREEN_600
                
            elif status["status"] == LicenseManager.STATUS_EXPIRED:
                self.status_text.value = "רישיון פג תוקף - מצב מוגבל"
                self.status_text.color = ft.colors.ORANGE_600
                
            else:
                self.status_text.value = "אין רישיון - מצב חינמי מוגבל"
                self.status_text.color = ft.colors.BLUE_600
            
            # Update feature list
            self._update_feature_list(status)
            
            # Update buttons
            if hasattr(self, 'deactivate_button') and self.deactivate_button:
                has_license = status["status"] in [LicenseManager.STATUS_VALID, LicenseManager.STATUS_EXPIRED]
                self.deactivate_button.visible = has_license
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error updating license status: {e}")
            self.status_text.value = "שגיאה בבדיקת סטטוס הרישיון"
            self.status_text.color = ft.colors.RED_600
            self.page.update()
    
    def _update_feature_list(self, status):
        """Update the feature list based on license status."""
        try:
            self.feature_list.controls.clear()
            
            license_type = status.get("type", LicenseManager.LICENSE_FREE)
            
            if license_type == LicenseManager.LICENSE_FREE or status["status"] != LicenseManager.STATUS_VALID:
                # Free tier features
                features = [
                    ("✅", "עד 3 קבצי IDF ביום"),
                    ("✅", "דוחות בסיסיים"),
                    ("✅", "נתוני מזג אוויר ישראליים"),
                    ("❌", "דוחות דירוג אנרגיה"),
                    ("❌", "דוחות מתקדמים"),
                    ("❌", "ייצוא Excel")
                ]
            elif license_type == LicenseManager.LICENSE_PROFESSIONAL:
                # Professional features
                features = [
                    ("✅", "עיבוד ללא הגבלה"),
                    ("✅", "כל סוגי הדוחות"),
                    ("✅", "דוחות דירוג אנרגיה"),
                    ("✅", "ייצוא PDF ו-Excel"),
                    ("✅", "תמיכה טכנית מועדפת"),
                    ("✅", "גישה לתכונות חדשות")
                ]
            else:
                # Enterprise features
                features = [
                    ("✅", "כל תכונות המקצועי"),
                    ("✅", "עד 10 משתמשים"),
                    ("✅", "API לאינטגרציה"),
                    ("✅", "מיתוג מותאם אישית"),
                    ("✅", "תמיכה 24/7"),
                    ("✅", "הדרכה אישית")
                ]
            
            for icon, feature in features:
                color = ft.colors.GREEN_600 if icon == "✅" else ft.colors.GREY_400
                self.feature_list.controls.append(
                    ft.Text(f"{icon} {feature}", size=14, color=color)
                )
            
        except Exception as e:
            logger.error(f"Error updating feature list: {e}")
    
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            self.page.set_clipboard(text)
            self._show_success("הועתק למשטח")
        except Exception as e:
            logger.error(f"Clipboard error: {e}")
            self._show_error("שגיאה בהעתקה למשטח")
    
    def _show_success(self, message: str):
        """Show success message."""
        try:
            snack = ft.SnackBar(
                content=ft.Text(message, color=ft.colors.WHITE),
                bgcolor=ft.colors.GREEN_600
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing success message: {e}")
    
    def _show_error(self, message: str):
        """Show error message."""
        try:
            snack = ft.SnackBar(
                content=ft.Text(message, color=ft.colors.WHITE),
                bgcolor=ft.colors.RED_600
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing error message: {e}")
    
    def _close_dialog(self, e):
        """Close the dialog."""
        if self.dialog:
            self.dialog.open = False
            self.page.update()


def show_trial_expired_dialog(page: ft.Page, on_license_activated: Optional[Callable] = None):
    """Show trial expired dialog with licensing options."""
    
    def activate_license(e):
        license_dialog = LicenseDialog(page, on_license_activated)
        dialog.open = False
        page.update()
        license_dialog.show_license_dialog(show_activation=True)
    
    def continue_free(e):
        dialog.open = False
        page.update()
        if on_license_activated:
            on_license_activated()
    
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("תקופת הניסיון הסתיימה", size=24, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Text(
                    "תקופת הניסיון של 14 ימים הסתיימה.",
                    size=16
                ),
                ft.Text(
                    "תוכל להמשיך להשתמש בתכונות הבסיסיות בחינם או לרכוש רישיון לגישה מלאה.",
                    size=14,
                    color=ft.colors.GREY_600
                ),
                ft.Divider(),
                ft.Text("תכונות זמינות במצב חינמי:", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("• עד 3 קבצי IDF ביום", size=12),
                ft.Text("• דוחות בסיסיים", size=12),
                ft.Text("• נתוני מזג אוויר ישראליים", size=12),
            ]),
            width=400,
            height=200
        ),
        actions=[
            ft.TextButton("המשך במצב חינמי", on_click=continue_free),
            ft.ElevatedButton(
                "הפעל רישיון",
                icon=ft.icons.VPN_KEY,
                on_click=activate_license,
                style=ft.ButtonStyle(
                    bgcolor=ft.colors.GREEN_600,
                    color=ft.colors.WHITE
                )
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    
    page.dialog = dialog
    dialog.open = True
    page.update()


def show_startup_license_check(page: ft.Page, on_continue: Optional[Callable] = None):
    """Show license check dialog on startup if needed."""
    try:
        status = license_manager.get_license_status()
        
        # If everything is fine, continue without dialog
        if status["status"] == LicenseManager.STATUS_VALID:
            if on_continue:
                on_continue()
            return
        
        # Show appropriate dialog based on status
        if status["status"] == LicenseManager.STATUS_EXPIRED:
            show_trial_expired_dialog(page, on_continue)
        else:
            # No license or error - continue to main app
            if on_continue:
                on_continue()
                
    except Exception as e:
        logger.error(f"Startup license check error: {e}")
        if on_continue:
            on_continue()