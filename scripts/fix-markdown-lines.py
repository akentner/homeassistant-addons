#!/usr/bin/env python3
"""
Lightweight Markdown Line Length Fixer
Fixes lines that are too long in Markdown files by breaking them appropriately.
"""
import re
import sys
import argparse
from pathlib import Path


def fix_long_lines(content: str, max_length: int = 120) -> str:
    """Fix lines that are too long in markdown content."""
    lines = content.splitlines()
    fixed_lines = []
    
    for line in lines:
        if len(line) <= max_length:
            fixed_lines.append(line)
            continue
            
        # Check if it's a markdown list item
        list_match = re.match(r'^(\s*[-*+]\s+\*\*[^*]+\*\*:\s*)', line)
        if list_match:
            prefix = list_match.group(1)
            remainder = line[len(prefix):]
            
            # Try to break at a sensible point
            if len(prefix) + len(remainder) > max_length:
                # Look for good break points: space before path, comma, etc.
                break_points = [
                    ' at ',
                    ' from ',
                    ' in ',
                    ', ',
                    ' - ',
                ]
                
                best_break = None
                for bp in break_points:
                    pos = remainder.find(bp)
                    if pos != -1 and len(prefix) + pos < max_length - 10:  # Leave some margin
                        best_break = pos + len(bp)
                        break
                
                if best_break:
                    line1 = prefix + remainder[:best_break].rstrip()
                    line2 = '  ' + remainder[best_break:].lstrip()  # Indent continuation
                    fixed_lines.extend([line1, line2])
                else:
                    # Fallback: break at max_length
                    break_at = max_length - len(prefix) - 10
                    line1 = prefix + remainder[:break_at].rstrip()
                    line2 = '  ' + remainder[break_at:].lstrip()
                    fixed_lines.extend([line1, line2])
            else:
                fixed_lines.append(line)
        else:
            # For other long lines, try to break at word boundaries
            if ' ' in line:
                words = line.split()
                current_line = words[0]
                
                for word in words[1:]:
                    if len(current_line) + len(word) + 1 <= max_length:
                        current_line += ' ' + word
                    else:
                        fixed_lines.append(current_line)
                        current_line = word
                
                if current_line:
                    fixed_lines.append(current_line)
            else:
                # Single long word - can't break it easily
                fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)


def main():
    parser = argparse.ArgumentParser(description='Fix long lines in Markdown files')
    parser.add_argument('files', nargs='*', help='Markdown files to process')
    parser.add_argument('--max-length', type=int, default=120, help='Maximum line length (default: 120)')
    parser.add_argument('--check', action='store_true', help='Only check, don\'t modify files')
    parser.add_argument('--glob', help='Glob pattern for files (e.g., "**/*.md")')
    
    args = parser.parse_args()
    
    files_to_process = []
    
    if args.glob:
        files_to_process = list(Path('.').glob(args.glob))
    elif args.files:
        files_to_process = [Path(f) for f in args.files]
    else:
        print("No files specified. Use --glob or provide file names.")
        return 1
    
    issues_found = 0
    files_fixed = 0
    
    for file_path in files_to_process:
        if not file_path.exists() or not file_path.is_file():
            continue
            
        try:
            content = file_path.read_text(encoding='utf-8')
            fixed_content = fix_long_lines(content, args.max_length)
            
            # Check if any changes were made
            original_lines = content.splitlines()
            fixed_lines = fixed_content.splitlines()
            
            has_long_lines = any(len(line) > args.max_length for line in original_lines)
            
            if has_long_lines:
                issues_found += 1
                print(f"Found long lines in: {file_path}")
                
                if not args.check:
                    file_path.write_text(fixed_content, encoding='utf-8')
                    files_fixed += 1
                    print(f"  ✅ Fixed: {file_path}")
                else:
                    # Show which lines are too long
                    for i, line in enumerate(original_lines, 1):
                        if len(line) > args.max_length:
                            print(f"  Line {i}: {len(line)} chars (max: {args.max_length})")
                            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    if args.check:
        print(f"\nFound {issues_found} files with long lines.")
        return 1 if issues_found > 0 else 0
    else:
        print(f"\nProcessed {len(files_to_process)} files, fixed {files_fixed} files.")
        return 0


if __name__ == '__main__':
    sys.exit(main())