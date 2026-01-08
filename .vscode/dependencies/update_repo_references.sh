#!/bin/bash

# Script to update repository references throughout the workspace
# This replaces hardcoded owner and repo names with actual values from git remote

set -e  # Exit on any error

echo "🔍 Getting repository information..."

# Get repository information from git remote
REPO_URL=$(git remote get-url origin)
NEW_OWNER=$(echo "$REPO_URL" | sed 's/.*\/\([^/]*\)\/[^/]*\.git$/\1/')
NEW_REPO_NAME=$(echo "$REPO_URL" | sed 's/.*\/\([^/]*\)\.git$/\1/')

echo "📋 Repository Details:"
echo "  Owner: $NEW_OWNER"
echo "  Repository: $NEW_REPO_NAME"
echo "  Full Name: $NEW_OWNER/$NEW_REPO_NAME"
echo ""

# Define the old values to replace
OLD_OWNER="git@github.com:marksieczkowski/ha-volkswagen.git"
OLD_REPO_NAME="ha-volkswagen"

echo "🔄 Replacements to be made:"
echo "  '$OLD_OWNER' → '$NEW_OWNER'"
echo "  '$OLD_REPO_NAME' → '$NEW_REPO_NAME'"
echo ""

# Function to safely replace text in files
replace_in_files() {
    local search_term="$1"
    local replace_term="$2"
    local description="$3"

    echo "🔍 Searching for '$search_term'..."

    # Find files containing the search term (exclude .git directory and binary files)
    local files_found=$(grep -r -l --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ "$search_term" . 2>/dev/null || true)

    if [ -z "$files_found" ]; then
        echo "  ✅ No files found containing '$search_term'"
        return
    fi

    echo "  📝 Files containing '$search_term':"
    echo "$files_found" | sed 's/^/    /'

    # Ask for confirmation
    read -p "  ❓ Replace '$search_term' with '$replace_term' in these files? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$files_found" | while IFS= read -r file; do
            if [ -f "$file" ]; then
                # Create backup
                cp "$file" "$file.bak"
                # Perform replacement (Mac-compatible sed)
                sed -i '' "s|$search_term|$replace_term|g" "$file"
                echo "    ✅ Updated: $file"
                # Remove backup if successful
                rm "$file.bak"
            fi
        done
    else
        echo "  ⏭️  Skipped replacement of '$search_term'"
    fi
    echo ""
}

# Function to show preview of changes
preview_changes() {
    local search_term="$1"
    local replace_term="$2"

    echo "🔍 Preview of changes for '$search_term' → '$replace_term':"
    grep -r -n --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ "$search_term" . 2>/dev/null | head -10 | while IFS= read -r line; do
        echo "  📄 $line"
    done
    echo ""
}

# Show current status
echo "🔍 Current repository references found:"
preview_changes "$OLD_OWNER" "$NEW_OWNER"
preview_changes "$OLD_REPO_NAME" "$NEW_REPO_NAME"

# Only proceed if there are actual changes to make
if [ "$OLD_OWNER" != "$NEW_OWNER" ] || [ "$OLD_REPO_NAME" != "$NEW_REPO_NAME" ]; then
    echo "🚀 Starting replacement process..."
    echo ""

    # Replace owner name first
    if [ "$OLD_OWNER" != "$NEW_OWNER" ]; then
        replace_in_files "$OLD_OWNER" "$NEW_OWNER" "owner name"
    fi

    # Replace repository name
    if [ "$OLD_REPO_NAME" != "$NEW_REPO_NAME" ]; then
        replace_in_files "$OLD_REPO_NAME" "$NEW_REPO_NAME" "repository name"
    fi

    echo "✅ Repository reference update complete!"
else
    echo "ℹ️  No changes needed - repository references are already correct."
fi

echo ""
echo "🎉 Done! Your workspace now uses the correct repository references."
