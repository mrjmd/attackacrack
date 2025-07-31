# Attack-a-Crack CRM UI/UX Style Guide

## Overview
This guide defines the visual and interaction standards for the Attack-a-Crack CRM application to ensure consistency across all interfaces.

## Design Principles
1. **Dark Theme First**: Optimized for extended use in various lighting conditions
2. **Information Density**: Maximize useful information while maintaining readability
3. **Consistent Interactions**: Predictable patterns across all features
4. **Mobile Responsive**: Works seamlessly on desktop and mobile devices

## Color Palette

### Primary Colors
- **Background Base**: `bg-gray-900` (#111827) - Sidebar, modals
- **Background Main**: `bg-gray-800` (#1F2937) - Main content area
- **Background Elevated**: `bg-gray-700` (#374151) - Cards, hover states

### Text Colors
- **Primary Text**: `text-white` - Main content
- **Secondary Text**: `text-gray-400` (#9CA3AF) - Supporting text, labels
- **Link Text**: `text-blue-400` (#60A5FA) - Interactive links
- **Link Hover**: `text-blue-300` (#93BBFE) - Hover state for links

### Status Colors
- **Success**: `text-green-400` / `bg-green-600` - Positive actions, success states
- **Warning**: `text-yellow-400` / `bg-yellow-600` - Warnings, pending states  
- **Error**: `text-red-500` / `bg-red-600` - Errors, destructive actions
- **Info**: `text-blue-400` / `bg-blue-600` - Informational messages

## Typography

### Font Sizes
- **Page Title**: `text-3xl font-bold` (30px bold)
- **Section Title**: `text-2xl font-bold` (24px bold)
- **Subsection**: `text-xl font-bold` (20px bold)
- **Body Text**: `text-base` (16px) - Default
- **Small Text**: `text-sm` (14px) - Labels, secondary info
- **Tiny Text**: `text-xs` (12px) - Timestamps, metadata

### Font Weights
- **Bold**: `font-bold` - Headings, emphasis
- **Semibold**: `font-semibold` - Subheadings
- **Medium**: `font-medium` - Navigation items
- **Normal**: Default - Body text

## Component Standards

### Buttons

#### Primary Button
```html
<button class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
    Primary Action
</button>
```

#### Secondary Button
```html
<button class="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
    Secondary Action
</button>
```

#### Danger Button
```html
<button class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline">
    Delete
</button>
```

#### Text Button
```html
<a href="#" class="text-gray-400 hover:text-white">Cancel</a>
```

### Form Elements

#### Text Input
```html
<input type="text" 
       class="shadow appearance-none border border-gray-600 rounded w-full py-2 px-3 bg-gray-700 text-white leading-tight focus:outline-none focus:shadow-outline">
```

#### Select Dropdown
```html
<select class="shadow appearance-none border border-gray-600 rounded w-full py-2 px-3 bg-gray-700 text-white leading-tight focus:outline-none focus:shadow-outline">
    <option>Option 1</option>
</select>
```

#### Label
```html
<label class="block text-gray-300 text-sm font-bold mb-2">Field Label</label>
```

### Cards & Containers

#### Basic Card
```html
<div class="bg-gray-800 p-6 rounded-lg shadow-lg">
    <!-- Card content -->
</div>
```

#### Table Container
```html
<div class="bg-gray-800 rounded-lg shadow-lg overflow-hidden">
    <table class="min-w-full">
        <!-- Table content -->
    </table>
</div>
```

### Navigation

#### Active Nav Item
```html
<a class="flex items-center px-4 py-3 text-sm font-medium rounded-lg bg-gray-700 text-blue-400">
    <span class="mr-3 text-lg">📊</span>
    Active Item
</a>
```

#### Inactive Nav Item
```html
<a class="flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors hover:bg-gray-700">
    <span class="mr-3 text-lg">📋</span>
    Inactive Item
</a>
```

## Layout Patterns

### Page Structure
```html
<div class="flex">
    <!-- Sidebar: 256px fixed width -->
    <div class="w-64 h-screen bg-gray-900 flex-shrink-0 overflow-y-auto">
        <!-- Navigation -->
    </div>
    
    <!-- Main Content -->
    <div class="flex-1 p-8 overflow-y-auto">
        <!-- Page content -->
    </div>
</div>
```

### Page Header
```html
<div class="flex justify-between items-center mb-8">
    <h1 class="text-3xl font-bold">Page Title</h1>
    <button class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
        Primary Action
    </button>
</div>
```

### Data Table
```html
<table class="min-w-full">
    <thead class="bg-gray-700">
        <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                Column Header
            </th>
        </tr>
    </thead>
    <tbody class="divide-y divide-gray-700">
        <tr class="hover:bg-gray-700">
            <td class="px-6 py-4 whitespace-nowrap">
                Cell Content
            </td>
        </tr>
    </tbody>
</table>
```

## Spacing Guidelines

### Padding
- **Large**: `p-8` (32px) - Page container
- **Medium**: `p-6` (24px) - Cards, modals
- **Small**: `p-4` (16px) - Compact sections
- **Tiny**: `p-2` (8px) - Inline elements

### Margins
- **Section Gap**: `mb-8` (32px) - Between major sections
- **Element Gap**: `mb-4` (16px) - Between related elements
- **Label Gap**: `mb-2` (8px) - Between labels and inputs

## Interactive States

### Hover Effects
- **Buttons**: Darken background color (e.g., `hover:bg-blue-700`)
- **Links**: Lighten text color (e.g., `hover:text-blue-300`)
- **Table Rows**: Add background (e.g., `hover:bg-gray-700`)

### Focus States
- **Inputs**: Use `focus:outline-none focus:shadow-outline`
- **Buttons**: Same as inputs for consistency

### Transitions
- **Navigation**: `transition-colors` for smooth color changes
- **All Interactive Elements**: Consider adding transitions for polish

## Icons & Emojis

### Navigation Icons
- Dashboard: 📊
- Messages: 💬
- Contacts: 👥
- Campaigns: 📢
- Settings: ⚙️

### Status Indicators
- Success: ✅
- Error: ❌
- Warning: ⚠️
- Info: ℹ️

## Responsive Design

### Breakpoints
- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

### Mobile Considerations
- Sidebar becomes hamburger menu
- Tables scroll horizontally
- Reduce padding on mobile: `p-4` instead of `p-8`

## Accessibility

### Requirements
- All interactive elements must be keyboard accessible
- Maintain sufficient color contrast (WCAG AA minimum)
- Provide appropriate ARIA labels where needed
- Focus indicators must be visible

### Best Practices
- Use semantic HTML elements
- Provide alt text for images
- Ensure form labels are properly associated
- Test with keyboard navigation

## Implementation Notes

1. **Consistency First**: When in doubt, follow existing patterns
2. **Tailwind Classes**: Use utility classes; avoid custom CSS
3. **Component Reuse**: Extract common patterns into templates
4. **Performance**: Minimize JavaScript; use CSS transitions
5. **Testing**: Verify on both desktop and mobile devices