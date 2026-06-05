# Brand/Style Presets Reference

## Preset Structure

Presets are JSON files stored in `~/.banana/presets/NAME.json`. Each contains:
- colors
- visual style
- typography
- lighting conditions
- mood descriptors
- default output settings

## Available Presets

**Tech-SaaS:** Professional palette of blues and whites with clean, minimal aesthetics and geometric typefaces suited to modern software brands.

**Luxury-Brand:** Sophisticated black, gold, and cream tones with elegant serif fonts and rich textures for exclusive, high-end positioning.

**Editorial-Magazine:** Stark black-and-white with red accents, bold photography, and condensed headlines for contemporary, impactful publications.

## How They Work

Presets serve as default values for design briefs. The system maps preset attributes to specific reasoning components:
- Colors → palette choices
- Style → visual foundation
- Typography → text treatment
- Lighting → mood atmosphere
- Mood → overall tone

**Important:** User instructions take precedence. If you request something contrary to a preset's settings, your direct request wins.

## Command Reference

```bash
# List all presets
banana preset list

# View preset details
banana preset show <name>

# Create new preset interactively
banana preset create

# Delete preset
banana preset delete <name>
```
