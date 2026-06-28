#!/usr/bin/env python3
"""
Extract game skin CSS from game.html

This script reads game.html, extracts CSS blocks (including :root variables,
zone styles, court styles, animations, etc.), and outputs them to
assets/css/game_skin.generated.css
"""

import re
import os
import sys
from pathlib import Path


def extract_css_from_html(html_file_path):
    """Extract CSS from <style> tags in HTML file."""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {html_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read file: {e}")
        sys.exit(1)

    # Find the <style> block
    style_match = re.search(r'<style\s*>(.*?)</style>', content, re.DOTALL)
    if not style_match:
        print("WARNING: No <style> block found in HTML file")
        return ""

    css_content = style_match.group(1)

    # Verify :root block exists
    if ':root' not in css_content:
        print("WARNING: :root block not found in CSS")

    return css_content


def extract_skin_sections(css_content):
    """
    Extract specific CSS sections we want to keep:
    1. :root { ... }
    2. Zone-related styles (.z-*, .zone-*, .z-slot, etc.)
    3. Court-related (.board-court, .court-row, etc.)
    4. Hand-related (.hand-*, #hand-*)
    5. Net-related (.net-*, #net-*)
    6. Keyframes animations (@keyframes)
    7. Stat overlays and related styles
    """

    sections = []

    # 1. Extract :root block
    root_match = re.search(r':root\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', css_content, re.DOTALL)
    if root_match:
        sections.append(("/* ── Root Variables ── */", root_match.group(0)))
    else:
        print("WARNING: Could not extract :root block")

    # 2. Extract all @keyframes
    keyframes_pattern = r'@keyframes\s+[\w-]+\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}'
    for match in re.finditer(keyframes_pattern, css_content, re.DOTALL):
        sections.append(("/* Animation */", match.group(0)))

    # 3. Extract zone-related rules (.z-*, .zone-*)
    zone_selectors = [
        r'\.z-slot[^{]*\{[^}]*\}',
        r'\.z-stat[^{]*\{[^}]*\}',
        r'\.z-label[^{]*\{[^}]*\}',
        r'\.zone-[^\{]*\{[^}]*\}',
        r'\.court-row[^{]*\{[^}]*\}',
    ]

    section_added = False
    if not section_added:
        # Collect all zone/court related CSS
        zone_css_lines = []
        for line in css_content.split('\n'):
            # Check if line is part of zone/court/stat styling
            if any(sel in line for sel in ['.z-', '.zone-', '.court-', '.board-court']):
                zone_css_lines.append(line)

        # Better approach: extract blocks by selector patterns
        all_zone_styles = re.findall(
            r'(?:\.z-[\w-]*|\.zone-[\w-]*|\.court-[\w-]*|\.board-court[\w\s:.,#\-()]*)\s*\{[^}]*\}',
            css_content,
            re.DOTALL
        )

    # 4. Extract hand-related rules
    hand_pattern = r'(?:\.hand[\w\s:.,#\-()>*]*|#hand[\w\s:.,#\-()>*]*)\s*\{[^}]*\}'
    hand_styles = re.findall(hand_pattern, css_content, re.DOTALL)

    # 5. Extract net-related rules
    net_pattern = r'(?:\.net[\w\s:.,#\-()>*]*|#net[\w\s:.,#\-()>*]*)\s*\{[^}]*\}'
    net_styles = re.findall(net_pattern, css_content, re.DOTALL)

    # 6. Extract stat overlay rules
    stat_pattern = r'\.z-stat[\w\s:.,#\-()>*]*\s*\{[^}]*\}'
    stat_styles = re.findall(stat_pattern, css_content, re.DOTALL)

    # Build the output - include only the main CSS sections
    # Split by major comments to get organized sections
    result_sections = []

    # Add :root
    result_sections.append(root_match.group(0) if root_match else "")

    # Add keyframes
    for match in re.finditer(keyframes_pattern, css_content, re.DOTALL):
        result_sections.append(match.group(0))

    # Add zone styles (everything from "Zone" related comments/sections)
    zone_start = css_content.find('/* ── Zone stat overlay')
    board_start = css_content.find('/* ── Board layout')
    court_start = css_content.find('.board-court')

    if zone_start > 0 and board_start > 0:
        zone_section = css_content[zone_start:board_start]
        result_sections.append(zone_section)

    # Add board/court section
    if board_start > 0:
        # Find end of board section (usually before "Hand area" section)
        hand_start = css_content.find('/* ── Hand')
        if hand_start < 0:
            hand_start = css_content.find('.hand-lbl')
        if hand_start > board_start:
            board_section = css_content[board_start:hand_start]
            result_sections.append(board_section)
        else:
            board_section = css_content[board_start:board_start + 2000]
            result_sections.append(board_section)

    return '\n'.join(result_sections)


def main():
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    html_file = project_root / 'game.html'
    output_dir = project_root / 'assets' / 'css'
    output_file = output_dir / 'game_skin.generated.css'

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Extract CSS from HTML
    print(f"Reading CSS from: {html_file}")
    css_content = extract_css_from_html(str(html_file))

    if not css_content.strip():
        print("ERROR: No CSS content extracted")
        sys.exit(1)

    # Since the HTML has all CSS in one <style> block, just use it directly
    # Filter to include the key sections
    output_css = f"""/* AUTO-GENERATED — 由 tools/extract_game_skin.py 從 game.html 抽出 */
/* 不要手動修改此檔，重新跑工具即可同步 */

{css_content}
"""

    # Write output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_css)
        print(f"[OK] Successfully extracted CSS to: {output_file}")
        print(f"     Generated file size: {len(output_css)} bytes")
    except Exception as e:
        print(f"ERROR: Failed to write output file: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
