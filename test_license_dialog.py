#!/usr/bin/env python3
"""
Test script to verify license dialog functionality
"""

import flet as ft
from utils.license_dialog import LicenseDialog

def main(page: ft.Page):
    page.title = "License Dialog Test"
    page.window_width = 800
    page.window_height = 600
    page.theme_mode = ft.ThemeMode.LIGHT
    
    def test_license_dialog(e):
        try:
            print("Testing license dialog...")
            license_dialog = LicenseDialog(page)
            license_dialog.show_license_dialog()
            print("✓ License dialog shown successfully!")
        except Exception as ex:
            print(f"✗ Error showing license dialog: {ex}")
            import traceback
            traceback.print_exc()
    
    page.add(
        ft.Column([
            ft.Text("License Dialog Test", size=30, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.ElevatedButton(
                "Test License Dialog",
                icon=ft.Icons.KEY,
                on_click=test_license_dialog,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE_500,
                    color=ft.Colors.WHITE
                )
            ),
            ft.Text("Click the button above to test the license dialog."),
            ft.Text("If no errors appear in console, the fix worked!", color=ft.Colors.GREEN_500)
        ])
    )

if __name__ == "__main__":
    print("Starting license dialog test...")
    ft.app(target=main)
    print("Test completed.")