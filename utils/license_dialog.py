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
        logger.info(f"=== SHOW LICENSE DIALOG CALLED (show_activation={show_activation}) ===")
        logger.info(f"Page object: {self.page}")
        
        try:
            logger.info("Creating dialog content...")
            dialog_content = self._create_dialog_content(show_activation)
            logger.info(f"Dialog content created: {type(dialog_content)}")
            
            logger.info("Creating AlertDialog...")
            self.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Text("ניהול רישיונות", size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, rtl=True),
                        ft.Icon(ft.Icons.SECURITY, size=28, color=ft.Colors.BLUE_600),
                    ], spacing=10, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                    padding=ft.padding.only(bottom=15)
                ),
                content=ft.Container(
                    content=dialog_content,
                    width=550,
                    height=500,
                    padding=ft.padding.all(0)
                ),
                actions=[
                    ft.Container(
                        content=ft.ElevatedButton(
                            "סגור",
                            icon=ft.Icons.CLOSE,
                            on_click=self._close_dialog,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREY_600,
                                color=ft.Colors.WHITE,
                                elevation=2,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shape=ft.RoundedRectangleBorder(radius=8)
                            ),
                            height=40
                        ),
                        padding=ft.padding.all(10)
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.CENTER,
                content_padding=ft.padding.all(20),
                title_padding=ft.padding.all(20),
            )
            logger.info(f"AlertDialog created: {self.dialog}")
            
            logger.info("Closing any existing dialogs...")
            # Close any existing dialog first using overlay
            for control in self.page.overlay[:]:
                if isinstance(control, ft.AlertDialog):
                    control.open = False
                    self.page.overlay.remove(control)
            
            logger.info("Adding dialog to overlay...")
            self.page.overlay.append(self.dialog)
            logger.info("Opening dialog...")
            self.dialog.open = True
            logger.info(f"Dialog open status: {self.dialog.open}")
            logger.info("Updating page...")
            self.page.update()
            logger.info("Page updated successfully")
            logger.info(f"Dialog in overlay: {self.dialog in self.page.overlay}")
            logger.info(f"Final dialog.open: {self.dialog.open}")
            logger.info("Dialog should now be visible!")
            
            # Update status
            logger.info("Updating license status...")
            self._update_license_status()
            logger.info("License status updated")
            
        except Exception as e:
            logger.error(f"Error showing license dialog: {e}")
            self._show_error("שגיאה בהצגת חלון הרישיון")
    
    def _create_dialog_content(self, show_activation: bool) -> ft.Container:
        """Create the main content of the license dialog."""
        
        # Current status section
        self.status_text = ft.Text(
            "בודק סטטוס רישיון...",
            size=16,
            color=ft.Colors.BLUE,
            text_align=ft.TextAlign.RIGHT,
            rtl=True
        )
        
        status_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=20, color=ft.Colors.BLUE_600),
                            ft.Text("סטטוס רישיון נוכחי", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, rtl=True),
                        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                        margin=ft.margin.only(bottom=10)
                    ),
                    ft.Container(
                        content=self.status_text,
                        padding=ft.padding.symmetric(vertical=8, horizontal=12),
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=8,
                        margin=ft.margin.only(bottom=15)
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.STAR_OUTLINE, size=18, color=ft.Colors.ORANGE_600),
                            ft.Text("תכונות זמינות:", size=16, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.RIGHT, rtl=True),
                        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                        margin=ft.margin.only(bottom=10)
                    ),
                    self._create_feature_list()
                ], spacing=5),
                padding=20,
                border_radius=12
            ),
            elevation=3,
            surface_tint_color=ft.Colors.BLUE_50
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
                spacing=12,
                tight=True,
                scroll=ft.ScrollMode.AUTO
            ),
            width=550,
            height=480,
            padding=ft.padding.all(10)
        )
    
    def _create_activation_section(self) -> ft.Card:
        """Create the license activation section."""
        
        # Create a separate label for better RTL control
        self.serial_key_label = ft.Text(
            "מפתח רישיון:",
            size=14,
            color=ft.Colors.GREY_700,
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            weight=ft.FontWeight.W_500
        )
        
        self.serial_key_field = ft.TextField(
            hint_text="XXXX-XXXX-XXXX-XXXX",
            max_length=19,  # Including dashes
            text_align=ft.TextAlign.CENTER,
            on_change=self._format_serial_key,
            border_radius=10,
            filled=True,
            bgcolor=ft.Colors.WHITE,
            border_color=ft.Colors.BLUE_200,
            focused_border_color=ft.Colors.BLUE_600,
            prefix_icon=ft.Icons.VPN_KEY,
            rtl=False  # License keys should be LTR for consistency
        )
        
        self.activate_button = ft.ElevatedButton(
            text="הפעל רישיון",
            icon=ft.Icons.CHECK_CIRCLE,
            on_click=self._activate_license,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                elevation=2,
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            height=45
        )
        
        self.deactivate_button = ft.ElevatedButton(
            text="בטל רישיון",
            icon=ft.Icons.CANCEL_OUTLINED,
            on_click=self._deactivate_license,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.RED_600,
                color=ft.Colors.WHITE,
                elevation=2,
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            height=45
        )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SETTINGS, size=20, color=ft.Colors.GREEN_600),
                            ft.Text("הפעלת רישיון", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, rtl=True),
                        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Container(
                        content=ft.Text(
                            "הזן מפתח רישיון לקבלת גישה מלאה לכל התכונות",
                            size=14,
                            color=ft.Colors.GREY_700,
                            text_align=ft.TextAlign.RIGHT,
                            rtl=True
                        ),
                        margin=ft.margin.only(bottom=15)
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=self.serial_key_label,
                                margin=ft.margin.only(bottom=8),
                                alignment=ft.alignment.center_right
                            ),
                            self.serial_key_field
                        ], spacing=0),
                        margin=ft.margin.only(bottom=20)
                    ),
                    ft.Container(
                        content=ft.Row([
                            self.deactivate_button,
                            self.activate_button
                        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, rtl=True),
                        margin=ft.margin.only(top=10)
                    ),
                ], spacing=5),
                padding=20,
                border_radius=12
            ),
            elevation=3,
            surface_tint_color=ft.Colors.GREEN_50
        )
    
    def _create_machine_id_section(self) -> ft.Card:
        """Create the machine ID section."""
        
        machine_id = license_manager.get_machine_id()
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.COMPUTER, size=20, color=ft.Colors.PURPLE_600),
                            ft.Text("מזהה מחשב", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, rtl=True),
                        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                        margin=ft.margin.only(bottom=8)
                    ),
                    ft.Container(
                        content=ft.Text(
                            "מזהה זה נדרש להפעלת הרישיון",
                            size=14,
                            color=ft.Colors.GREY_700,
                            text_align=ft.TextAlign.CENTER,
                            rtl=True
                        ),
                        margin=ft.margin.only(bottom=15)
                    ),
                    ft.Container(
                        content=ft.TextField(
                            value=machine_id,
                            read_only=True,
                            text_align=ft.TextAlign.CENTER,
                            border_color=ft.Colors.PURPLE_200,
                            bgcolor=ft.Colors.GREY_50,
                            border_radius=10,
                            text_style=ft.TextStyle(
                                size=12,
                                weight=ft.FontWeight.W_500,
                                font_family="monospace"
                            ),
                            rtl=False  # Machine ID should be LTR
                        ),
                        margin=ft.margin.only(bottom=15)
                    ),
                    ft.Container(
                        content=ft.ElevatedButton(
                            text="העתק למשטח",
                            icon=ft.Icons.CONTENT_COPY,
                            on_click=lambda _: self._copy_to_clipboard(machine_id),
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.BLUE_600,
                                color=ft.Colors.WHITE,
                                elevation=2,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shape=ft.RoundedRectangleBorder(radius=8)
                            ),
                            height=40
                        ),
                        alignment=ft.alignment.center
                    )
                ], spacing=5),
                padding=20,
                border_radius=12
            ),
            elevation=3,
            surface_tint_color=ft.Colors.PURPLE_50
        )
    
    def _create_feature_list(self) -> ft.Container:
        """Create the feature list display."""
        
        self.feature_list = ft.Column(
            spacing=5,
            tight=True
        )
        
        return ft.Container(
            content=ft.Container(
                content=self.feature_list,
                bgcolor=ft.Colors.GREY_50,
                border_radius=10,
                padding=12,
                border=ft.border.all(1, ft.Colors.GREY_200)
            ),
            height=120
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
            logger.info("=== LICENSE ACTIVATION STARTED ===")
            
            if not self.serial_key_field or not self.serial_key_field.value:
                logger.warning("No serial key entered")
                self._show_error("אנא הזן מפתח רישיון")
                return
            
            serial_key = self.serial_key_field.value.strip()
            logger.info(f"Attempting to activate license: {serial_key[:8]}...")
            
            # Show loading with detailed feedback
            self.activate_button.text = "🔄 מפעיל..."
            self.activate_button.disabled = True
            self.page.update()
            
            # Show status message
            self._show_info("🔍 מתחבר לשרת רישיונות...")
            
            # Activate license
            logger.info("Calling license_manager.activate_license...")
            success, message = license_manager.activate_license(serial_key)
            logger.info(f"License activation result: success={success}, message={message}")
            
            if success:
                logger.info("=" * 50)
                logger.info("LICENSE ACTIVATION SUCCESSFUL!")
                logger.info("=" * 50)
                self._show_success(f"✅ {message}")
                logger.info("Updating license status display...")
                self._update_license_status()
                logger.info("Clearing input field...")
                # Clear the input field
                self.serial_key_field.value = ""
                self.page.update()
                logger.info("License activation UI updates completed")
                
                # Automatically refresh UI without asking user
                self._auto_refresh_after_activation()
                logger.info("Auto-refresh after activation completed")
            else:
                logger.warning(f"License activation failed: {message}")
                self._show_error(f"❌ {message}")
            
        except Exception as ex:
            logger.error(f"License activation error: {ex}")
            import traceback
            logger.error(traceback.format_exc())
            self._show_error(f"שגיאה בהפעלת הרישיון: {ex}")
        
        finally:
            # Reset button
            logger.info("Resetting activation button")
            self.activate_button.text = "הפעל רישיון"
            self.activate_button.disabled = False
            self.page.update()
            logger.info("=== LICENSE ACTIVATION COMPLETED ===")
    
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
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING, size=28, color=ft.Colors.RED_600),
                        ft.Text("אישור ביטול רישיון", size=20, weight=ft.FontWeight.BOLD, rtl=True),
                    ], spacing=10, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                    padding=ft.padding.only(bottom=15)
                ),
                content=ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(
                                    "האם אתה בטוח שברצונך לבטל את הרישיון?",
                                    size=16,
                                    text_align=ft.TextAlign.CENTER,
                                    weight=ft.FontWeight.W_500,
                                    rtl=True
                                ),
                                ft.Text(
                                    "התוכנה תעבור למצב מוגבל עם פחות תכונות.",
                                    size=14,
                                    color=ft.Colors.GREY_700,
                                    text_align=ft.TextAlign.CENTER,
                                    rtl=True
                                ),
                            ], spacing=10),
                            padding=20,
                            border_radius=12
                        ),
                        elevation=3,
                        surface_tint_color=ft.Colors.RED_50
                    ),
                    width=350,
                    height=100
                ),
                actions=[
                    ft.Container(
                        content=ft.Row([
                            ft.ElevatedButton(
                                "אשר ביטול",
                                icon=ft.Icons.DELETE_FOREVER,
                                on_click=confirm_deactivate,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.RED_600,
                                    color=ft.Colors.WHITE,
                                    elevation=2,
                                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                height=40
                            ),
                            ft.ElevatedButton(
                                "בטל",
                                icon=ft.Icons.CANCEL,
                                on_click=lambda _: setattr(confirm_dialog, 'open', False) or self.page.update(),
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.GREY_600,
                                    color=ft.Colors.WHITE,
                                    elevation=2,
                                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                height=40
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, rtl=True),
                        padding=ft.padding.all(10)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.CENTER,
                content_padding=ft.padding.all(20),
                title_padding=ft.padding.all(20),
            )
            
            self.page.overlay.append(confirm_dialog)
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
                self.status_text.color = ft.Colors.GREEN_500
                
            elif status["status"] == LicenseManager.STATUS_EXPIRED:
                self.status_text.value = "רישיון פג תוקף - מצב מוגבל"
                self.status_text.color = ft.Colors.ORANGE_500
                
            else:
                self.status_text.value = "אין רישיון - מצב חינמי מוגבל"
                self.status_text.color = ft.Colors.BLUE_500
            
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
            self.status_text.color = ft.Colors.RED_500
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
                is_enabled = icon == "✅"
                color = ft.Colors.GREEN_600 if is_enabled else ft.Colors.GREY_500
                bgcolor = ft.Colors.GREEN_50 if is_enabled else ft.Colors.GREY_50
                
                self.feature_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if is_enabled else ft.Icons.CANCEL,
                                size=16,
                                color=ft.Colors.GREEN_600 if is_enabled else ft.Colors.GREY_400
                            ),
                            ft.Container(
                                content=ft.Text(
                                    feature,
                                    size=13,
                                    color=color,
                                    weight=ft.FontWeight.W_500 if is_enabled else ft.FontWeight.W_400,
                                    text_align=ft.TextAlign.RIGHT,
                                    rtl=True
                                ),
                                expand=True
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "●" if is_enabled else "○",
                                    size=12,
                                    color=ft.Colors.GREEN_600 if is_enabled else ft.Colors.GREY_400,
                                    weight=ft.FontWeight.BOLD
                                ),
                                width=20
                            ),
                        ], spacing=8, rtl=True),
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        border_radius=6,
                        bgcolor=bgcolor,
                        border=ft.border.all(1, ft.Colors.GREEN_200 if is_enabled else ft.Colors.GREY_200)
                    )
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
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.GREEN_500
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing success message: {e}")
    
    def _show_info(self, message: str):
        """Show info message."""
        try:
            snack = ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.BLUE_500
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing info message: {e}")
    
    def _show_error(self, message: str):
        """Show error message."""
        try:
            snack = ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.RED_500
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing error message: {e}")
    
    def _show_activation_success_dialog(self):
        """Show success dialog with restart/refresh options after license activation."""
        try:
            logger.info("=== SHOWING ACTIVATION SUCCESS DIALOG ===")
            
            def refresh_ui(e):
                """Refresh UI without restart."""
                logger.info("User chose to refresh UI")
                success_dialog.open = False
                self.dialog.open = False  # Close license dialog too
                self.page.update()
                
                # Refresh the main UI to reflect new license status
                self._refresh_main_ui()
                
                # Also trigger a callback if one was provided (to update main UI)
                if self.on_license_changed:
                    logger.info("Calling on_license_changed callback for UI refresh")
                    self.on_license_changed()
                
                # Show success message
                self._show_success("הרישיון הופעל בהצלחה! הממשק עודכן.")
            
            def restart_app(e):
                """Restart the application."""
                logger.info("User chose to restart application")
                success_dialog.open = False
                self.dialog.open = False  # Close license dialog too
                self.page.update()
                
                # Show restart message
                self._show_info("מאתחל את האפליקציה...")
                
                # Import restart functionality
                try:
                    from utils.update_manager import UpdateManager
                    update_manager = UpdateManager(
                        status_callback=lambda msg: logger.info(f"Restart: {msg}"),
                        progress_callback=lambda p: None
                    )
                    
                    # Schedule restart after short delay
                    import threading
                    def delayed_restart():
                        import time
                        time.sleep(2)
                        update_manager._restart_application()
                    
                    threading.Thread(target=delayed_restart, daemon=True).start()
                    
                except Exception as ex:
                    logger.error(f"Error restarting: {ex}")
                    self._show_error("שגיאה באתחול - אנא סגור ופתח את התוכנה ידנית")
            
            # Create success dialog
            success_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE, size=32, color=ft.Colors.GREEN_600),
                        ft.Text("רישיון הופעל בהצלחה!", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600, rtl=True),
                    ], spacing=12, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
                    padding=ft.padding.only(bottom=20)
                ),
                content=ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Container(
                                    content=ft.Text(
                                        "הרישיון שלך הופעל בהצלחה! כעת תוכל ליהנות מכל התכונות הזמינות.",
                                        size=16,
                                        text_align=ft.TextAlign.CENTER,
                                        color=ft.Colors.GREY_800,
                                        rtl=True
                                    ),
                                    margin=ft.margin.only(bottom=20)
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "בחר איך להמשיך:",
                                        size=15,
                                        weight=ft.FontWeight.W_600,
                                        text_align=ft.TextAlign.CENTER,
                                        color=ft.Colors.BLUE_700,
                                        rtl=True
                                    ),
                                    margin=ft.margin.only(bottom=15)
                                ),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Icon(ft.Icons.REFRESH, size=18, color=ft.Colors.BLUE_600),
                                                ft.Text("רענן ממשק (מומלץ)", size=14, weight=ft.FontWeight.W_500, rtl=True),
                                            ], spacing=8, rtl=True),
                                            padding=ft.padding.symmetric(vertical=5)
                                        ),
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Icon(ft.Icons.RESTART_ALT, size=18, color=ft.Colors.ORANGE_600),
                                                ft.Text("אתחל מחדש", size=14, weight=ft.FontWeight.W_500, rtl=True),
                                            ], spacing=8, rtl=True),
                                            padding=ft.padding.symmetric(vertical=5)
                                        ),
                                    ], spacing=8),
                                    bgcolor=ft.Colors.BLUE_50,
                                    border_radius=8,
                                    padding=12,
                                    border=ft.border.all(1, ft.Colors.BLUE_200)
                                )
                            ], spacing=10),
                            padding=20,
                            border_radius=12
                        ),
                        elevation=3,
                        surface_tint_color=ft.Colors.GREEN_50
                    ),
                    width=400,
                    height=200
                ),
                actions=[
                    ft.Container(
                        content=ft.Row([
                            ft.ElevatedButton(
                                "רענן ממשק",
                                icon=ft.Icons.REFRESH,
                                on_click=refresh_ui,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.BLUE_600,
                                    color=ft.Colors.WHITE,
                                    elevation=2,
                                    padding=ft.padding.symmetric(horizontal=24, vertical=12),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                height=45
                            ),
                            ft.ElevatedButton(
                                "אתחל מחדש",
                                icon=ft.Icons.RESTART_ALT,
                                on_click=restart_app,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.ORANGE_600,
                                    color=ft.Colors.WHITE,
                                    elevation=2,
                                    padding=ft.padding.symmetric(horizontal=24, vertical=12),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                height=45
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                        padding=ft.padding.all(15)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.CENTER,
                content_padding=ft.padding.all(20),
                title_padding=ft.padding.all(20),
            )
            
            # Show the success dialog
            self.page.overlay.append(success_dialog)
            success_dialog.open = True
            self.page.update()
            logger.info("Activation success dialog displayed")
            
        except Exception as ex:
            logger.error(f"Error showing activation success dialog: {ex}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _auto_refresh_after_activation(self):
        """Automatically refresh UI after license activation without user interaction."""
        try:
            logger.info("=== AUTO-REFRESHING UI AFTER ACTIVATION ===")
            
            # Close license dialog
            self.dialog.open = False
            self.page.update()
            
            # Refresh the main UI to reflect new license status
            self._refresh_main_ui()
            
            # Also trigger a callback if one was provided (to update main UI)
            if self.on_license_changed:
                logger.info("Calling on_license_changed callback for UI refresh")
                self.on_license_changed()
            
            # Show success message
            self._show_success("הרישיון הופעל בהצלחה! הממשק עודכן אוטומטית.")
            
            logger.info("Auto-refresh completed successfully")
            
        except Exception as e:
            logger.error(f"Error in auto-refresh after activation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback to simple success message
            self._show_success("הרישיון הופעל בהצלחה!")
    
    def _refresh_main_ui(self):
        """Refresh the main UI to reflect new license status."""
        try:
            logger.info("=== REFRESHING MAIN UI FOR NEW LICENSE ===")
            
            # Find and update license button if possible
            # This is a simple refresh - more complex updates can be added
            if hasattr(self.page, 'controls'):
                logger.info("Triggering page update to refresh license-dependent UI elements")
                self.page.update()
                
                # Additional refresh logic can be added here:
                # - Update status displays
                # - Refresh available features
                # - Update tooltips, etc.
                
            logger.info("Main UI refresh completed")
            
        except Exception as ex:
            logger.error(f"Error refreshing main UI: {ex}")
    
    def _close_dialog(self, e):
        """Close the dialog - using same approach as working update dialog."""
        logger.info("=== DIALOG CLOSE BUTTON CLICKED ===")
        if self.dialog:
            logger.info("Closing dialog using simple approach...")
            self.dialog.open = False
            self.page.update()
            logger.info("Dialog closed successfully")


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
        title=ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER, size=28, color=ft.Colors.ORANGE_600),
                ft.Text("תקופת הניסיון הסתיימה", size=24, weight=ft.FontWeight.BOLD, rtl=True),
            ], spacing=10, alignment=ft.MainAxisAlignment.CENTER, rtl=True),
            padding=ft.padding.only(bottom=15)
        ),
        content=ft.Container(
            content=ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Text(
                                "תקופת הניסיון של 14 ימים הסתיימה.",
                                size=16,
                                text_align=ft.TextAlign.CENTER,
                                weight=ft.FontWeight.W_500,
                                rtl=True
                            ),
                            margin=ft.margin.only(bottom=15)
                        ),
                        ft.Container(
                            content=ft.Text(
                                "תוכל להמשיך להשתמש בתכונות הבסיסיות בחינם או לרכוש רישיון לגישה מלאה.",
                                size=14,
                                color=ft.Colors.GREY_700,
                                text_align=ft.TextAlign.CENTER,
                                rtl=True
                            ),
                            margin=ft.margin.only(bottom=20)
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.STAR_OUTLINE, size=18, color=ft.Colors.ORANGE_600),
                                        ft.Text("תכונות זמינות במצב חינמי:", size=16, weight=ft.FontWeight.BOLD, rtl=True),
                                    ], spacing=8, rtl=True),
                                    margin=ft.margin.only(bottom=10)
                                ),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Text("●", size=12, color=ft.Colors.GREEN_600),
                                                ft.Text("עד 3 קבצי IDF ביום", size=13, color=ft.Colors.GREY_700, rtl=True)
                                            ], spacing=8, rtl=True),
                                            padding=ft.padding.symmetric(vertical=3)
                                        ),
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Text("●", size=12, color=ft.Colors.GREEN_600),
                                                ft.Text("דוחות בסיסיים", size=13, color=ft.Colors.GREY_700, rtl=True)
                                            ], spacing=8, rtl=True),
                                            padding=ft.padding.symmetric(vertical=3)
                                        ),
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Text("●", size=12, color=ft.Colors.GREEN_600),
                                                ft.Text("נתוני מזג אוויר ישראליים", size=13, color=ft.Colors.GREY_700, rtl=True)
                                            ], spacing=8, rtl=True),
                                            padding=ft.padding.symmetric(vertical=3)
                                        ),
                                    ], spacing=2),
                                    bgcolor=ft.Colors.GREY_50,
                                    border_radius=8,
                                    padding=ft.padding.all(12),
                                    border=ft.border.all(1, ft.Colors.GREY_200)
                                )
                            ], spacing=5)
                        )
                    ], spacing=5),
                    padding=20,
                    border_radius=12
                ),
                elevation=3,
                surface_tint_color=ft.Colors.ORANGE_50
            ),
            width=450,
            height=280
        ),
        actions=[
            ft.Container(
                content=ft.Row([
                    ft.ElevatedButton(
                        "המשך במצב חינמי",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=continue_free,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.GREY_600,
                            color=ft.Colors.WHITE,
                            elevation=2,
                            padding=ft.padding.symmetric(horizontal=20, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=8)
                        ),
                        height=40
                    ),
                    ft.ElevatedButton(
                        "הפעל רישיון",
                        icon=ft.Icons.KEY,
                        on_click=activate_license,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.GREEN_600,
                            color=ft.Colors.WHITE,
                            elevation=2,
                            padding=ft.padding.symmetric(horizontal=20, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=8)
                        ),
                        height=40
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, rtl=True),
                padding=ft.padding.all(10)
            )
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
        content_padding=ft.padding.all(20),
        title_padding=ft.padding.all(20),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def show_startup_license_check(page: ft.Page, on_continue: Optional[Callable] = None):
    """Show license check dialog on startup if needed."""
    logger.info("=" * 80)
    logger.info("=== STARTUP LICENSE CHECK FUNCTION CALLED ===")
    logger.info(f"Page object: {page}")
    logger.info(f"Page controls count: {len(page.controls) if page.controls else 0}")
    logger.info(f"Page overlay count: {len(page.overlay) if page.overlay else 0}")
    logger.info(f"on_continue callback: {on_continue}")
    logger.info(f"on_continue callback type: {type(on_continue)}")
    
    try:
        logger.info("Getting license status...")
        status = license_manager.get_license_status()
        logger.info(f"License status received: {status}")
        
        # If license is valid, continue without dialog
        if status["status"] == LicenseManager.STATUS_VALID:
            logger.info("=" * 50)
            logger.info("LICENSE IS VALID - BUILDING UI DIRECTLY")
            logger.info("=" * 50)
            if on_continue:
                logger.info("Calling on_continue callback for valid license...")
                on_continue()
                logger.info("on_continue callback completed for valid license")
            else:
                logger.warning("No on_continue callback provided!")
            return
        
        # No valid license - show license dialog for activation (mandatory)
        logger.info("=" * 50)
        logger.info(f"LICENSE STATUS '{status['status']}' - SHOWING MANDATORY LICENSE DIALOG")
        logger.info("=" * 50)
        
        # Create a wrapper callback that only continues after successful activation
        def license_activation_callback():
            logger.info("=" * 40)
            logger.info("LICENSE ACTIVATION CALLBACK CALLED")
            logger.info("Checking license status after activation...")
            
            # Re-check license status
            new_status = license_manager.get_license_status()
            if new_status["status"] == LicenseManager.STATUS_VALID:
                logger.info("License is now valid - building main UI")
                if on_continue:
                    on_continue()
                else:
                    logger.warning("No on_continue callback provided!")
            else:
                logger.warning("License still not valid after activation dialog")
                # Keep showing dialog until valid license
                show_startup_license_check(page, on_continue)
            logger.info("=" * 40)
        
        dialog = LicenseDialog(page, license_activation_callback)
        logger.info("LicenseDialog created for mandatory activation")
        logger.info("Calling show_license_dialog...")
        dialog.show_license_dialog(show_activation=True)
        logger.info("show_license_dialog call completed")
                
    except Exception as e:
        logger.error(f"Startup license check error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # On error, show license dialog for activation
        try:
            logger.info("Exception occurred - showing license dialog as fallback")
            # Create a wrapper callback that always ensures the main UI is built
            def ensure_ui_callback():
                logger.info("Fallback license dialog closed - ensuring main UI is built")
                if on_continue:
                    on_continue()
            
            dialog = LicenseDialog(page, ensure_ui_callback)
            dialog.show_license_dialog(show_activation=True)
        except Exception as e2:
            logger.error(f"Failed to show fallback license dialog: {e2}")
            logger.error(traceback.format_exc())
            # Last resort - just continue
            if on_continue:
                logger.info("Last resort - calling on_continue directly")
                on_continue()