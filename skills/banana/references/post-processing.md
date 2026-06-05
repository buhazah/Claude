# Post-Processing Pipeline Reference

This guide covers image manipulation techniques for generated images using ImageMagick and FFmpeg.

## Key Prerequisites

Before starting, verify tool availability with `which magick`, `which convert`, and `which ffmpeg`.
- Debian/Ubuntu: `sudo apt install imagemagick`
- macOS: `brew install imagemagick`

## Core Capabilities

### Platform-Specific Resizing
- Instagram: 1080×1080
- Twitter/X headers: 1500×500
- YouTube thumbnails: 1280×720
- LinkedIn banners: 1584×396
- Favicons: 16×16, 32×32, 64×64

### Background Handling
Multiple approaches for transparency work:
- Remove solid colors with adjustable fuzz levels
- Anti-aliasing edge cleanup
- **Green screen pipeline**: Generate with bright green backgrounds, then remove programmatically (workaround for Gemini's lack of transparent background support)

### Format Conversions
- PNG → WebP
- PNG → JPEG
- PNG → AVIF

### Color Adjustments
- Contrast enhancement
- Temperature shifts (warm/cool)
- Desaturation and grayscale
- Sepia effects

### Compositing Operations
- Watermark overlays
- Side-by-side comparisons
- Vertical stacking
- Borders and rounded corners

### Batch Processing
Loop operations across directories for multi-file workflows.

## Advanced Features

### Animation
- GIFs via ImageMagick
- MP4 video sequences via FFmpeg

### Quality Assessment
Verify dimensions and file sizes before delivery.

## 4K Note
Modern generative models supporting 4K output (up to 4096×4096) often eliminate the need for upscaling post-processing, producing better detail retention than upscaled lower-resolution images.
