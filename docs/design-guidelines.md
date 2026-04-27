# Trip Monitoring System -- Design Guidelines

> Complete design system documentation for the Trip Monitoring application.
> Last updated: April 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [CSS Variables (Design Tokens)](#2-css-variables-design-tokens)
3. [Typography System](#3-typography-system)
4. [Component Classes](#4-component-classes)
5. [Utility Classes](#5-utility-classes)
6. [Responsive Design](#6-responsive-design)
7. [Animations and Transitions](#7-animations-and-transitions)
8. [Usage Examples](#8-usage-examples)
9. [Accessibility Guidelines](#9-accessibility-guidelines)
10. [Best Practices](#10-best-practices)
11. [File Structure](#11-file-structure)

---

## 1. Overview

### Design Philosophy

The Trip Monitoring System uses a **4-color palette** built around a teal-and-coral theme, layered on top of **Bootstrap 5.2.3**. Custom styles override Bootstrap defaults through CSS custom properties and targeted selectors to produce a cohesive, modern look with soft rounded corners, subtle shadows, and smooth transitions.

### Technology Stack

| Layer       | Technology                           |
|-------------|--------------------------------------|
| CSS Framework | Bootstrap 5.2.3                     |
| Icon Library | Bootstrap Icons 1.11.3              |
| Charts      | Apache ECharts 5.5.0                |
| Typefaces   | Outfit (300-700), system fallbacks   |
| CSS Custom Properties | Yes (see Variables section) |

### Source Files

| File                                   | Purpose                                      |
|----------------------------------------|----------------------------------------------|
| `static/style.css`                     | Global design system overrides               |
| `static/css/dashboard.css`             | Dashboard-specific responsive + animation    |
| `templates/base.html`                  | Base template with nav, footer, CDN links    |

---

## 2. CSS Variables (Design Tokens)

All custom properties are defined in `:root` within `static/style.css`.

### Color Palette

| Variable              | Value       | Swatch | Usage                                |
|-----------------------|-------------|--------|--------------------------------------|
| `--primary`           | `#4ECDC4`   | Teal   | Main actions, links, active states   |
| `--primary-dark`      | `#2E8B82`   | Teal (dark) | Hover states, emphasis           |
| `--secondary`         | `#1A535C`   | Deep sea | Headings, body text, navbar bg    |
| `--accent`            | `#FF6B6B`   | Coral  | Destructive actions, highlights     |
| `--accent-light`      | `#FF8E8E`   | Coral (light) | Destructive hover              |
| `--background`        | `#F7FFF7`   | Bubble white | Page background               |
| `--white`             | `#FFFFFF`   | White  | Card backgrounds, text on dark bg   |
| `--gray-light`        | `#E8ECEE`   | Gray   | Borders, card headers, input groups |
| `--gray-medium`       | `#6B7B7F`   | Gray (med) | Muted text, secondary badges   |

### Extended Palette (used in badges, alerts, buttons)

| Semantic name | Bootstrap class | Mapped color | Notes |
|---|---|---|---|
| Success / Positive | `.bg-success`, `.btn-success` | `var(--primary)` (#4ECDC4) | Same as primary |
| Danger / Destructive | `.bg-danger`, `.btn-danger` | `var(--accent)` (#FF6B6B) | Coral |
| Warning / Caution | `.bg-warning`, `.btn-warning` | `#FFE66D` | Sunny yellow |
| Info | `.bg-info`, `.btn-info` | `var(--primary)` (#4ECDC4) | Same as primary |
| Neutral | `.bg-secondary` | `var(--gray-medium)` (#6B7B7F) | Gray |
| Primary | `.bg-primary` | `var(--secondary)` (#1A535C) | Deep sea |

### Spacing and Sizing

| Token | Value | Context |
|---|---|---|
| Card border-radius | `16px` | `.card` |
| Button border-radius | `12px` | `.btn` |
| Small button border-radius | `10px` | `.btn-sm` |
| Input border-radius | `12px` | `.form-control`, `.form-select` |
| Badge border-radius | `8px` | `.badge` |
| Alert border-radius | `12px` | `.alert` |
| Modal border-radius | `16px` | `.modal-content` |
| Pagination link border-radius | `10px` | `.page-link` |
| Container max-width | `1350px` | `.container` |

### Shadows

| Context | Value |
|---|---|
| Card default | `0 4px 20px rgba(26, 83, 92, 0.08)` |
| Card hover | `0 6px 25px rgba(26, 83, 92, 0.12)` |
| Navbar | `0 2px 10px rgba(26, 83, 92, 0.15)` |
| Dropdown menu | `0 4px 20px rgba(0, 0, 0, 0.1)` |
| Modal | `0 10px 40px rgba(26, 83, 92, 0.15)` |
| Primary button hover | `0 4px 15px rgba(78, 205, 196, 0.4)` |
| Danger button hover | `0 4px 15px rgba(255, 107, 107, 0.4)` |

---

## 3. Typography System

### Font Stack

```css
font-family: 'Outfit', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
```

Loaded via Google Fonts with weights: 300 (Light), 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold).

### Headings

| Element | Size (desktop) | Size (mobile) | Weight | Color |
|---|---|---|---|---|
| `h1` | `2rem` | `1.5rem` | 700 | `var(--secondary)` |
| `h2` | `1.75rem` | `1.25rem` | 700 | `var(--secondary)` |
| `h3` | Bootstrap default | Bootstrap default | 700 | `var(--secondary)` |
| `h4` | Bootstrap default | Bootstrap default | 700 | `var(--secondary)` |
| `h5` | Bootstrap default | Bootstrap default | 700 | `var(--secondary)` |
| `h6` | Bootstrap default | Bootstrap default | 700 | `var(--secondary)` |

### Body Text

| Property | Value |
|---|---|
| Color | `var(--secondary)` (#1A535C) |
| Background | `var(--background)` (#F7FFF7) |
| Min-height | `100vh` |

### Component Text Styles

| Component | Weight | Color | Notes |
|---|---|---|---|
| `.navbar-brand` | 700 | `var(--white)` | Size: 1.4rem |
| `.nav-link` | 500 | `rgba(255,255,255,0.9)` | In navbar |
| `.card-header` | 600 | `var(--secondary)` | Inherit size |
| `.form-label` | 600 | `var(--secondary)` | |
| `.badge` | 600 | Contextual | Padded: 0.5rem 0.75rem |
| `.dropdown-item` | 500 | Inherited | |
| `.modal-title` | 700 | `var(--secondary)` | |

### Links

```css
a { color: var(--primary); text-decoration: none; }
a:hover { color: var(--primary-dark); }
```

---

## 4. Component Classes

### 4.1 Navigation Bar

```html
<nav class="navbar navbar-expand-lg navbar-dark">
```

| Property | Value |
|---|---|
| Background | `var(--secondary)` (#1A535C) |
| Shadow | `0 2px 10px rgba(26, 83, 92, 0.15)` |
| Brand weight | 700, 1.4rem |
| Brand hover | `var(--primary)` |
| Nav link hover | `var(--primary)` |
| Toggler border | `rgba(255, 255, 255, 0.3)` |

**Dropdown menus** have no visible border, 12px radius, 8px padding, and a subtle shadow.

### 4.2 Cards

```html
<div class="card">
    <div class="card-header">Title</div>
    <div class="card-body">Content</div>
</div>
```

| Property | Value |
|---|---|
| Border | None |
| Border-radius | `16px` |
| Shadow | `0 4px 20px rgba(26, 83, 92, 0.08)` |
| Background | `var(--white)` |
| Margin-bottom | `1.5rem` (1rem on mobile) |
| Hover lift | `translateY(-2px)` + enhanced shadow |
| Header bg | `var(--gray-light)` |
| Header border-bottom | `2px solid var(--primary)` |
| Header padding | `1rem 1.5rem` |

**Dashboard section cards** (`.section-card`): 0.5rem radius, lighter shadow, compact header.

### 4.3 Buttons

All buttons share: `border-radius: 12px`, `font-weight: 600`, `padding: 0.625rem 1.5rem`, `transition: all 0.2s ease`, `border: none`.

| Class | Background | Text | Hover BG | Hover shadow |
|---|---|---|---|---|
| `.btn-primary` | `var(--primary)` | White | `var(--primary-dark)` | Teal glow |
| `.btn-success` | `var(--primary)` | White | `var(--primary-dark)` | Teal glow |
| `.btn-danger` | `var(--accent)` | White | `var(--accent-light)` | Coral glow |
| `.btn-secondary` | `var(--gray-light)` | `var(--secondary)` | `#D8DCDF` | None |
| `.btn-info` | `var(--primary)` | White | `var(--primary-dark)` | None |
| `.btn-warning` | `#FFE66D` | `var(--secondary)` | Bootstrap default | None |

**Hover behavior**: All colored buttons lift (`translateY(-2px)`) on hover.

**Small buttons** (`.btn-sm`): `0.375rem 0.875rem`, `0.875rem` font, `10px` radius. On mobile: `0.375rem 0.625rem`, `0.75rem` font.

### 4.4 Forms

#### Text Inputs / Selects

```html
<input type="text" class="form-control" placeholder="...">
<select class="form-select">...</select>
```

| Property | Value |
|---|---|
| Border | `2px solid var(--gray-light)` |
| Border-radius | `12px` |
| Padding | `0.75rem 1rem` |
| Font-size | `1rem` |
| Focus border | `var(--primary)` |
| Focus ring | `0 0 0 3px rgba(78, 205, 196, 0.15)` |

#### Validation States

| Class | Border color | Feedback color |
|---|---|---|
| `.is-invalid` | `var(--accent)` | `var(--accent)` |
| `.is-valid` | `var(--primary)` | `var(--primary)` |

#### Input Groups

```html
<div class="input-group">
    <input class="form-control" ...>
    <button class="btn btn-primary">Search</button>
</div>
```

- Input group text: gray-light background and border, 12px left radius.
- Last child in input group gets 12px right radius.

#### Checkboxes

```html
<div class="form-check">
    <input class="form-check-input" type="checkbox">
    <label class="form-check-label">Label</label>
</div>
```

- Border: `2px solid var(--gray-medium)`, 6px radius.
- Checked: `var(--primary)` background and border.

### 4.5 Tables

```html
<div class="table-responsive">
    <table class="table table-striped table-hover table-sm table-compact">
```

| Property | Value |
|---|---|
| Border-radius | `12px` (with overflow hidden) |
| Header bg | `var(--gray-light)` |
| Header border-bottom | `2px solid var(--primary)` |
| Header text color | `var(--secondary)`, weight 600 |
| Cell padding | `1rem` |
| Row hover | `rgba(78, 205, 196, 0.05)` |
| Row transition | `background-color 0.2s ease` |
| Compact font (`.table-compact`) | `0.85rem`, header `white-space: nowrap` |
| Responsive font (mobile) | `0.875rem` |

### 4.6 Badges

```html
<span class="badge bg-success">Active</span>
<span class="badge bg-danger">Cancelled</span>
<span class="badge bg-warning">Pending</span>
<span class="badge bg-info">Info</span>
<span class="badge bg-primary">Trip #1</span>
<span class="badge bg-secondary">Not Set</span>
```

| Property | Value |
|---|---|
| Font-weight | 600 |
| Padding | `0.5rem 0.75rem` |
| Border-radius | `8px` |

**Color mapping**: All Bootstrap badge colors are remapped to the design palette (see Extended Palette table in Section 2).

### 4.7 Alerts

```html
<div class="alert alert-info alert-dismissible fade show" role="alert">
    Message text
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
```

| Type | Background | Left border |
|---|---|---|
| `.alert-info` | `rgba(78, 205, 196, 0.1)` | `var(--primary)` |
| `.alert-success` | `rgba(78, 205, 196, 0.1)` | `var(--primary)` |
| `.alert-danger` | `rgba(255, 107, 107, 0.1)` | `var(--accent)` |
| `.alert-warning` | `rgba(255, 230, 109, 0.2)` | `#FFE66D` |

All alerts: no visible border, 12px border-radius, 4px solid left border, 1rem 1.5rem padding.

### 4.8 Modals

```html
<div class="modal fade" id="myModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Title</h5>
                <button class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">...</div>
            <div class="modal-footer">
                <button class="btn btn-secondary">Cancel</button>
                <button class="btn btn-primary">Confirm</button>
            </div>
        </div>
    </div>
</div>
```

| Part | Background | Border-radius | Padding |
|---|---|---|---|
| `.modal-content` | White | `16px` | -- |
| `.modal-header` | `var(--gray-light)` | `16px 16px 0 0` | `1.25rem 1.5rem` |
| `.modal-body` | White | -- | `1.5rem` |
| `.modal-footer` | `var(--gray-light)` | `0 0 16px 16px` | `1rem 1.5rem` |

### 4.9 Pagination

```html
<nav aria-label="Page navigation">
    <ul class="pagination justify-content-center">
        <li class="page-item"><a class="page-link" href="#">&laquo;</a></li>
        <li class="page-item active"><span class="page-link">1</span></li>
        <li class="page-item"><a class="page-link" href="#">2</a></li>
    </ul>
</nav>
```

| Property | Value |
|---|---|
| Link color | `var(--primary)` |
| Link border | `2px solid var(--gray-light)` |
| Link border-radius | `10px` |
| Link margin | `0 0.25rem` |
| Active bg | `var(--primary)` |
| Hover bg | `var(--primary)` with white text |

### 4.10 Progress Bars

```html
<div class="progress">
    <div class="progress-bar" style="width: 75%"></div>
</div>
```

- Height: `12px`, border-radius `10px`.
- Track bg: `var(--gray-light)`.
- Fill bg: `var(--primary)`.

### 4.11 Nav Tabs

```html
<ul class="nav nav-tabs">
    <li class="nav-item"><a class="nav-link active" href="#">Tab 1</a></li>
    <li class="nav-item"><a class="nav-link" href="#">Tab 2</a></li>
</ul>
```

- Bottom border: `2px solid var(--gray-light)`.
- Active tab: bottom border `var(--primary)`, text color `var(--primary)`.
- Hover: bottom border `var(--gray-light)`, text `var(--secondary)`.

### 4.12 Footer

```html
<footer class="text-center text-lg-start">
    <div class="text-center p-3">
        <strong>&copy; 2026 Trip Monitoring System</strong>
    </div>
</footer>
```

- Background: `var(--gray-light)`.
- Top border: `2px solid var(--primary)`.
- Margin-top: `3rem`.
- Padding: `2rem 0`.

### 4.13 Dashboard-Specific Components

#### Dashboard Header

```html
<div class="dashboard-header d-flex justify-content-between align-items-center">
    <h4>Dashboard</h4>
    <small>Last updated...</small>
</div>
```

- Background: `linear-gradient(135deg, #1e293b 0%, #334155 100%)`.
- Color: white.
- Padding: `1.25rem 1.5rem`.
- Border-radius: `0.5rem`.

#### Section Title

```html
<h2 class="section-title">Title</h2>
```

- Size: `1.1rem`, weight 700.
- Color: `#1e293b`.
- Left border accent: `4px solid #3b82f6`.
- Left padding: `0.75rem`.

#### Loading Overlay

```html
<div class="loading-overlay">
    <div class="spinner-border loading-spinner"></div>
</div>
```

- Fixed full-screen overlay with `rgba(255,255,255,0.8)` background.
- Spinner color: `var(--primary)`.

#### Error Banner

```html
<div id="errorBanner" class="alert alert-danger alert-dismissible fade show
     position-fixed top-0 start-50 translate-middle-x">
```

- Slide-down animation (`slideDown` keyframe, 0.3s ease-out).

---

## 5. Utility Classes

### Custom Scrollbar

Applied globally. Width: `10px`. Track: `var(--gray-light)`. Thumb: `var(--primary)` with 10px radius. Thumb hover: `var(--primary-dark)`.

### Text Color Overrides (scoped)

These override Bootstrap text colors within `.table` and `.navbar` to match the design palette:

| Class | Color |
|---|---|
| `.table .text-primary` / `.navbar .text-primary` | `var(--primary)` |
| `.table .text-success` / `.navbar .text-success` | `var(--primary)` |
| `.table .text-danger` / `.navbar .text-danger` | `var(--accent)` |
| `.table .text-info` / `.navbar .text-info` | `var(--primary)` |

### Common Bootstrap Utilities Used

| Class | Usage |
|---|---|
| `.d-flex`, `.justify-content-between`, `.align-items-center` | Page headers, toolbar rows |
| `.mb-3`, `.mb-4` | Standard spacing between sections |
| `.mt-3`, `.mt-4`, `.mt-5` | Top margin |
| `.row`, `.col-md-3/4/6` | Form grid layouts |
| `.w-100` | Full-width buttons |
| `.text-center`, `.text-muted` | Text alignment and muted color |
| `.btn-group`, `.btn-group-sm` | Button clusters in schedule view |
| `.shadow` | Login card shadow |
| `.position-fixed` | Error banner positioning |
| `.gap-2`, `.gap-3` | Flex gap spacing |

---

## 6. Responsive Design

### Breakpoints

The application uses Bootstrap's standard breakpoints:

| Breakpoint | Width | Typical device |
|---|---|---|
| xs | < 576px | Small phones |
| sm | >= 576px | Large phones |
| md | >= 768px | Tablets |
| lg | >= 992px | Small desktops |
| xl | >= 1200px | Desktops |

### Breakpoint-Specific Rules

#### Below 768px (`max-width: 767.98px`)

- `h1` shrinks from `2rem` to `1.5rem`.
- `h2` shrinks from `1.75rem` to `1.25rem`.
- `.btn-sm` shrinks to `0.75rem` font and `0.375rem 0.625rem` padding.
- `.card` margin-bottom reduces to `1rem`.
- Table font reduces to `0.875rem` inside `.table-responsive`.
- KPI cards stack vertically (full width columns).
- Gauge chart columns go full width.
- Secondary chart axis hides.

#### Below 992px (`max-width: 991px`)

- Dashboard charts reduce height to `250px !important`.

#### Below 768px (dashboard charts)

- Dashboard charts reduce height to `200px !important`.

### Responsive Patterns Used in Templates

1. **Search bars** use `col-md-4` so they stack on mobile.
2. **Page headers** use `d-flex justify-content-between align-items-center flex-wrap gap-2`.
3. **Tables** always wrapped in `.table-responsive`.
4. **Forms** use `row` + `col-md-*` grid for multi-column desktop, single-column mobile.
5. **Reports cards** use `col-md-4` grid with `h-100` for equal height.

---

## 7. Animations and Transitions

### Global Transitions

| Element | Property | Duration | Easing |
|---|---|---|---|
| `.btn` | all | 0.2s | ease |
| `.card` | transform, box-shadow | 0.2s | ease |
| `.table tbody tr` | background-color | 0.2s | ease |
| `.nav-link` | color | 0.2s | ease |
| `.dropdown-item` | background-color | 0.2s | ease |
| `.form-control`, `.form-select` | all | 0.2s | ease |
| `.page-link` | all | 0.2s | ease |

### Keyframe Animations

#### Dashboard: Slide Down (Error Banner)

```css
@keyframes slideDown {
    from { transform: translateY(-100%); opacity: 0; }
    to   { transform: translateY(0);     opacity: 1; }
}
/* Applied via: #errorBanner.show { animation: slideDown 0.3s ease-out; } */
```

### Hover Effects

| Element | Effect |
|---|---|
| `.card` | Lifts 2px, shadow intensifies |
| `.btn-primary` | Lifts 2px, glow shadow |
| `.btn-danger` | Lifts 2px, coral glow shadow |
| `.table tbody tr` | Subtle teal tint background |
| `.page-link` | Teal background with white text |
| `.dropdown-item` | Gray-light background |

---

## 8. Usage Examples

### Standard Page Layout

Every page extends `base.html` and follows this pattern:

```html
{% extends "base.html" %}

{% block title %}Page Title - Trip Monitoring System{% endblock %}

{% block content %}
<!-- Page Header -->
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1><i class="bi bi-icon"></i> Page Title</h1>
    <div>
        <a href="#" class="btn btn-primary">
            <i class="bi bi-plus-circle"></i> Action
        </a>
    </div>
</div>

<!-- Content Card -->
<div class="card">
    <div class="card-header">
        <h5>Section Title</h5>
    </div>
    <div class="card-body">
        <!-- Content here -->
    </div>
</div>
{% endblock %}
```

### Search + Data Table Pattern

```html
<div class="card">
    <div class="card-body">
        <form method="get" class="mb-3">
            <div class="row">
                <div class="col-md-4">
                    <div class="input-group">
                        <input type="text" class="form-control" name="search"
                               placeholder="Search..." value="{{ search }}">
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-search"></i> Search
                        </button>
                        {% if search %}
                        <a href="#" class="btn btn-outline-secondary">Clear</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        </form>

        <div class="table-responsive">
            <table class="table table-striped table-hover table-sm table-compact">
                <thead>
                    <tr><th>Column</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Data</td>
                        <td><span class="badge bg-success">Active</span></td>
                        <td>
                            <a href="#" class="btn btn-sm btn-outline-primary">
                                <i class="bi bi-pencil"></i> Edit
                            </a>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
```

### Modal Form Pattern

```html
<!-- Trigger button -->
<button class="btn btn-primary" data-bs-toggle="modal"
        data-bs-target="#myModal">Open</button>

<!-- Modal -->
<div class="modal fade" id="myModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Modal Title</h5>
                <button class="btn-close" data-bs-dismiss="modal"
                        aria-label="Close"></button>
            </div>
            <form method="post" action="/endpoint">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="field" class="form-label">Label</label>
                        <input type="text" class="form-control" id="field"
                               name="field" required>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary"
                            data-bs-dismiss="modal">Cancel</button>
                    <button type="submit" class="btn btn-primary">Save</button>
                </div>
            </form>
        </div>
    </div>
</div>
```

### Form Layout (Multi-Column)

```html
<form method="post">
    <div class="row">
        <div class="col-md-4 mb-3">
            <label for="field1" class="form-label">Field 1</label>
            <input type="text" class="form-control" id="field1" name="field1">
        </div>
        <div class="col-md-4 mb-3">
            <label for="field2" class="form-label">Field 2</label>
            <select class="form-select" id="field2" name="field2">
                <option value="">Select...</option>
                <option value="a">Option A</option>
            </select>
        </div>
        <div class="col-md-4 mb-3">
            <label for="field3" class="form-label">Field 3</label>
            <input type="date" class="form-control" id="field3" name="field3">
        </div>
    </div>
    <div class="d-flex justify-content-between">
        <a href="#" class="btn btn-secondary">Cancel</a>
        <button type="submit" class="btn btn-primary">Save</button>
    </div>
</form>
```

### Flash Message Pattern

```html
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
            <div class="alert alert-{{ category }} alert-dismissible fade show"
                 role="alert">
                {{ message }}
                <button type="button" class="btn-close"
                        data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        {% endfor %}
    {% endif %}
{% endwith %}
```

---

## 9. Accessibility Guidelines

### Focus Indicators

The design system provides visible focus indicators:

- **Form inputs**: 3px ring `rgba(78, 205, 196, 0.15)` on focus.
- **Buttons and links**: Standard browser focus ring.
- **Keyboard navigation**: All interactive elements reachable via Tab.

### ARIA Attributes Used

| Attribute | Context |
|---|---|
| `role="alert"` | Flash messages, alert banners |
| `aria-label="Close"` | Dismiss buttons on alerts and modals |
| `aria-label="Previous"` / `"Next"` | Pagination arrows |
| `aria-label="Page navigation"` | Pagination nav wrapper |
| `aria-labelledby` | Modal titles |
| `aria-hidden="true"` | Modal backdrops, decorative elements |
| `tabindex="-1"` | Modal root elements |

### Semantic HTML Patterns

- `<nav>` for navigation and pagination.
- `<header>`, `<main>`, `<footer>` for page structure.
- `<table>` with proper `<thead>` / `<tbody>`.
- `<form>` with associated `<label>` elements (via `for` attribute).
- `<button>` (not `<div>`) for all clickable actions.
- `role="group"` for button groups.

### Color Contrast

| Foreground | Background | Context | Status |
|---|---|---|---|
| `var(--secondary)` (#1A535C) | `var(--background)` (#F7FFF7) | Body text | Pass |
| `var(--white)` (#FFFFFF) | `var(--primary)` (#4ECDC4) | Primary buttons | Check at point of use |
| `var(--white)` (#FFFFFF) | `var(--secondary)` (#1A535C) | Navbar | Pass |
| `var(--secondary)` (#1A535C) | `var(--gray-light)` (#E8ECEE) | Card headers | Pass |
| `var(--secondary)` (#1A535C) | `#FFE66D` | Warning badges | Pass |

### Recommendations

1. **Always use `<label>` with form inputs** -- never rely on placeholder alone.
2. **Provide text alternatives for icons** using `aria-label` or accompanying text.
3. **Ensure focus-visible is present** for keyboard users.
4. **Use `btn-close` with `aria-label="Close"`** on all dismiss buttons.
5. **Test with screen readers** after adding new components.
6. **Maintain a minimum 4.5:1 contrast ratio** for normal text, 3:1 for large text.

---

## 10. Best Practices

### Adding New Pages

1. Extend `base.html` using `{% extends "base.html" %}`.
2. Set `{% block title %}` with the page name suffix.
3. Use `{% block content %}` for main page content.
4. Use `{% block styles %}` for page-specific CSS (see dashboard pattern).
5. Use `{% block scripts %}` for page-specific JavaScript.

### Adding New Components

1. Use existing CSS variables (`var(--primary)`, etc.) -- never hard-code colors.
2. Match existing border-radius: `16px` for cards/modals, `12px` for buttons/inputs, `8px` for badges.
3. Add `transition: all 0.2s ease` to interactive elements.
4. Provide hover states that include a subtle lift or shadow change.
5. Wrap tables in `.table-responsive`.

### Form Design

1. Always use `.form-label` with `for` attribute matching input `id`.
2. Use `.form-text` for helper text below inputs.
3. Use `.input-group` for search bars with action buttons.
4. Use `.is-invalid` and `.invalid-feedback` for validation errors.
5. Group form rows using `.row` > `.col-md-*` grid.

### Table Design

1. Use `.table-striped .table-hover` for data tables.
2. Add `.table-sm .table-compact` for dense data.
3. Always wrap in `.table-responsive`.
4. Use badges for status columns.
5. Use `.btn-sm .btn-outline-*` for row action buttons.
6. Add `style="white-space: nowrap;"` to action columns.

### Icon Usage

Use Bootstrap Icons with the `<i>` element:

```html
<i class="bi bi-pencil"></i> Edit
<i class="bi bi-trash"></i> Delete
<i class="bi bi-search"></i> Search
<i class="bi bi-plus-circle"></i> Add
<i class="bi bi-arrow-left"></i> Back
```

Common icons in the application: `bi-truck`, `bi-calendar-check`, `bi-graph-up`, `bi-speedometer2`, `bi-person-gear`, `bi-clock-history`, `bi-fuel-pump`, `bi-download`, `bi-upload`, `bi-exclamation-triangle`.

### Color Usage Rules

1. **Primary actions** (submit, save, add): `.btn-primary`.
2. **Destructive actions** (delete, cancel, remove): `.btn-danger` or `.btn-outline-danger`.
3. **Neutral actions** (cancel, close, back): `.btn-secondary`.
4. **Success status**: `.badge.bg-success` (teal).
5. **Error/danger status**: `.badge.bg-danger` (coral).
6. **Warning/pending status**: `.badge.bg-warning` (yellow).
7. **Informational**: `.badge.bg-info` (teal).
8. **Neutral/secondary**: `.badge.bg-secondary` (gray).

### Performance Considerations

1. Bootstrap and Icons loaded via CDN -- ensure CDN links are current.
2. ECharts loaded globally in `base.html` -- only used on dashboard.
3. Google Fonts loaded with `display=swap` -- no FOIT.
4. Use `defer` on page-specific scripts.
5. Minimize inline styles -- prefer utility classes.

---

## 11. File Structure

```
static/
  style.css                    # Global design system (all pages)
  css/
    dashboard.css              # Dashboard-specific responsive + animation

templates/
  base.html                    # Base template (nav, footer, CDN links)
  dashboard.html               # Dashboard (extends base)
  login.html                   # Login page
  view_data.html               # Data table with search + pagination + modal
  add_data.html                # CSV upload form
  edit_data.html               # Edit form (multi-column layout)
  manage_vehicles.html         # CRUD table + modals pattern
  manage_users.html            # CRUD table + pagination + modal
  reports.html                 # Report cards grid + results tables
  view_schedule.html           # Complex schedule view with multiple modals
  add_schedule.html            # Multi-step schedule creation
  time_logs.html               # Time log table + modals
  ...                          # Other templates follow same patterns
```
