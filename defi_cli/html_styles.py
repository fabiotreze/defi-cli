"""
HTML Report CSS Styles
======================

All CSS for the DeFi CLI position analysis report.
Separated from html_generator.py for maintainability.

The status-badge colours are parameterised because they depend
on the position's in-range / out-of-range state.
"""

import re as _re


def _validate_css_color(value: str) -> str:
    """Validate a CSS color value to prevent style injection (CWE-79)."""
    if _re.fullmatch(r"#[0-9a-fA-F]{3,8}", value):
        return value
    raise ValueError(f"Invalid CSS color: {value!r}")


def build_css(status_bg: str, status_border: str, status_text_color: str) -> str:
    """Return the complete ``<style>`` block for the position report.

    Args:
        status_bg:         Background colour for the status badge.
        status_border:     Border colour for the status badge.
        status_text_color: Text colour for the status badge.
    """
    # CWE-79: validate colour parameters before CSS interpolation
    status_bg = _validate_css_color(status_bg)
    status_border = _validate_css_color(status_border)
    status_text_color = _validate_css_color(status_text_color)
    return f"""    <style>
        :root {{
            --primary: #3b82f6;
            --primary-light: #60a5fa;
            --success: #10b981;
            --success-light: #34d399;
            --warning: #f59e0b;
            --warning-light: #fbbf24;
            --danger: #ef4444;
            --danger-light: #f87171;
            --info: #06b6d4;
            --info-light: #22d3ee;
            --purple: #8b5cf6;
            --purple-light: #a78bfa;
            --bg: #f8fafc;
            --bg-light: #ffffff;
            --card: #ffffff;
            --card-hover: #fefefe;
            --border: #e1e5e9;
            --border-light: #f1f5f9;
            --text: #1e293b;
            --text-light: #64748b;
            --text-lighter: #94a3b8;
            --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --radius: 12px;
            --radius-lg: 16px;

            /* ── Typography Scale ──────────────────────── */
            --fs-2xs: 0.7rem;     /* 11.2px – fine print, footnotes          */
            --fs-xs:  0.75rem;    /* 12px   – labels, uppercase captions     */
            --fs-sm:  0.85rem;    /* 13.6px – secondary text, descriptions   */
            --fs-md:  0.875rem;   /* 14px   – compact body, tile subtitles   */
            --fs-base: 0.95rem;   /* 15.2px – body text, regular content     */
            --fs-lg:  1.1rem;     /* 17.6px – data values, prices, emphasis  */
            --fs-xl:  1.25rem;    /* 20px   – section titles, key metrics    */
            --fs-2xl: 1.5rem;     /* 24px   – card headings, tab titles      */
            --fs-3xl: 2rem;       /* 32px   – hero numbers, primary stat     */
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            margin: 0;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: var(--text);
            line-height: 1.7;
            font-size: 15px;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            position: relative;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--purple) 100%);
            color: white;
            padding: 3rem 2rem;
            border-radius: var(--radius-lg);
            margin-bottom: 2rem;
            text-align: center;
            box-shadow: var(--shadow-xl);
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, rgba(255,255,255,0.1) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.1) 75%), 
                        linear-gradient(45deg, rgba(255,255,255,0.1) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.1) 75%);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
            opacity: 0.3;
        }}

        .session {{
            background: var(--card);
            border: 1px solid var(--border-light);
            border-radius: var(--radius);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            position: relative;
        }}
        
        .session:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
            border-color: var(--primary-light);
        }}

        .session-title {{
            font-size: var(--fs-2xl);
            font-weight: 800;
            margin: 0 0 2rem 0;
            color: var(--text);
            position: relative;
            padding-bottom: 1rem;
            padding-left: 1rem;
        }}
        
        .session-title::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(180deg, var(--primary), var(--purple));
            border-radius: 2px;
        }}
        
        .session-title::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 1rem;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 50%, transparent 100%);
            border-radius: 1px;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }}

        .metric-card {{
            background: linear-gradient(135deg, var(--card) 0%, #f8fafc 100%);
            border: 1px solid var(--border-light);
            border-radius: var(--radius);
            padding: 1.5rem 1rem;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .metric-card:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
            border-color: var(--primary-light);
        }}
        
        .metric-card::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--primary-light), var(--purple));
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }}
        
        .metric-card:hover::after {{
            transform: scaleX(1);
        }}

        .metric-value {{
            font-size: var(--fs-xl);
            font-weight: 600;
            color: var(--primary);
        }}

        .price-range-bar {{
            position: relative;
            width: 100%;
            height: 8px;
            background: linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #22c55e 100%);
            border-radius: 4px;
            margin: 1rem 0;
        }}

        .current-price-indicator {{
            position: absolute;
            top: -4px;
            width: 16px;
            height: 16px;
            background: white;
            border: 3px solid var(--primary);
            border-radius: 50%;
            transform: translateX(-50%);
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}

        .range-labels {{
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
            font-size: var(--fs-xs);
            color: var(--text-light);
        }}

        .strategy-gauge {{
            position: relative;
            width: 100%;
            height: 80px;
            background: #f1f5f9;
            border-radius: 8px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}

        .gauge-fill {{
            height: 100%;
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            transition: width 0.3s ease;
            border-radius: 8px;
        }}

        .gauge-label {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 4px rgba(0,0,0,0.6), 0 0 8px rgba(0,0,0,0.3);
            background: rgba(0,0,0,0.25);
            padding: 0.2rem 0.75rem;
            border-radius: 4px;
        }}

        .tile {{
            background: linear-gradient(135deg, var(--card) 0%, var(--bg-light) 100%);
            border: 1px solid var(--border-light);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 1.25rem;
            box-shadow: var(--shadow);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}
        
        .tile::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
            transition: left 0.5s;
        }}

        @media (hover: hover) {{
            .tile:hover {{
                transform: translateY(-4px);
                box-shadow: var(--shadow-lg);
                border-color: var(--primary-light);
            }}
            
            .tile:hover::before {{
                left: 100%;
            }}
        }}

        .tile-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
        }}

        .tile-icon {{
            width: 56px;
            height: 56px;
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.75rem;
            margin-right: 1.25rem;
            flex-shrink: 0;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            position: relative;
            z-index: 2;
        }}
        
        .tile-icon::before {{
            content: '';
            position: absolute;
            inset: -2px;
            border-radius: var(--radius);
            padding: 2px;
            background: linear-gradient(45deg, var(--primary-light), var(--purple-light));
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask-composite: exclude;
        }}

        .tile-title {{
            font-size: var(--fs-lg);
            font-weight: 600;
            color: var(--text);
        }}

        .progress-bar {{
            width: 100%;
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--primary), #3b82f6);
            border-radius: 3px;
            transition: width 0.5s ease;
        }}

        .status-indicator {{
            display: inline-flex;
            align-items: center;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: var(--fs-sm);
            font-weight: 600;
            margin: 0.5rem 0;
        }}

        .status-in-range {{
            background: linear-gradient(135deg, #dcfce7, #bbf7d0);
            color: #15803d;
            border: 1px solid #86efac;
        }}

        .status-out-range {{
            background: linear-gradient(135deg, #fef2f2, #fecaca);
            color: #dc2626;
            border: 1px solid #fca5a5;
        }}

        .apy-display {{
            background: linear-gradient(135deg, #fef3c7, #fde68a);
            border: 1px solid #facc15;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            margin: 1rem 0;
        }}

        .apy-value {{
            font-size: var(--fs-3xl);
            font-weight: 700;
            color: #b45309;
        }}

        .comparison-bars {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin: 1rem 0;
        }}

        .comparison-item {{
            text-align: center;
            padding: 1rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}

        .comparison-value {{
            font-size: var(--fs-2xl);
            font-weight: 600;
            margin: 0.5rem 0;
        }}

        .comparison-label {{
            font-size: var(--fs-sm);
            color: var(--text-light);
        }}

        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: var(--fs-sm);
            font-weight: 500;
            background: {status_bg};
            border: 1px solid {status_border};
            color: {status_text_color};
        }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-light);
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}

        .consent-info {{
            background: linear-gradient(135deg, #fefce8, #fef9c3);
            border: 3px solid #f59e0b;
            border-radius: 12px;
            padding: 1.25rem;
            margin: 1.5rem 0;
            font-size: var(--fs-base);
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.15);
        }}

        /* ===== Table of Contents ===== */
        .toc {{
            background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
            border: 1px solid #bae6fd;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin: 0 0 2rem 0;
        }}
        .toc-title {{
            font-size: var(--fs-base);
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 0.75rem;
        }}
        .toc-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.25rem;
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .toc-list a {{
            text-decoration: none;
            color: var(--text);
            font-size: var(--fs-sm);
            padding: 0.4rem 0.75rem;
            border-radius: 6px;
            display: block;
            transition: background 0.2s;
        }}
        .toc-list a:hover {{
            background: rgba(37, 99, 235, 0.1);
            color: var(--primary);
        }}

        /* ===== Collapsible Sections ===== */
        .collapsible-toggle {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            user-select: none;
            background: none;
            border: none;
            width: 100%;
            text-align: left;
            font: inherit;
            color: inherit;
            padding: 0;
        }}
        .collapsible-toggle .chevron {{
            transition: transform 0.3s ease;
            font-size: var(--fs-xl);
            color: var(--text-light);
        }}
        .collapsible-toggle.expanded .chevron {{
            transform: rotate(180deg);
        }}
        .collapsible-body {{
            overflow: hidden;
            transition: max-height 0.4s ease, opacity 0.3s ease;
            max-height: 0;
            opacity: 0;
        }}
        .collapsible-body.expanded {{
            max-height: none;
            opacity: 1;
        }}

        /* ===== Copy Button ===== */
        .copy-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            background: #e0f2fe;
            border: 1px solid #bae6fd;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: var(--fs-2xs);
            cursor: pointer;
            color: var(--primary);
            transition: background 0.2s;
            vertical-align: middle;
            margin-left: 0.5rem;
        }}
        .copy-btn:hover {{
            background: #bae6fd;
        }}
        .copy-btn:focus-visible, .collapsible-toggle:focus-visible {{
            outline: 2px solid var(--primary);
            outline-offset: 2px;
        }}
        /* ===== Health Score Gauge ===== */
        .health-gauge-container {{
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }}
        .health-gauge-ring {{
            position: relative;
            width: 120px;
            height: 120px;
            flex-shrink: 0;
        }}
        .health-gauge-ring svg {{
            transform: rotate(-90deg);
        }}
        .health-gauge-ring .score-text {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }}
        .health-gauge-ring .score-number {{
            font-size: var(--fs-3xl);
            font-weight: 800;
            line-height: 1;
        }}
        .health-gauge-ring .score-label {{
            font-size: var(--fs-2xs);
            color: var(--text-light);
            text-transform: uppercase;
        }}
        .health-breakdown {{
            display: grid;
            gap: 0.4rem;
            flex: 1;
        }}
        .health-row {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: var(--fs-sm);
        }}
        .health-row-bar {{
            flex: 1;
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
        }}
        .health-row-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }}

        /* ===== Tab Navigation Styles ===== */
        .tab-container {{
            margin-top: 1.5rem;
        }}
        
        .tab-nav {{
            display: flex;
            flex-wrap: nowrap;
            gap: 0.25rem;
            margin-bottom: 1.5rem;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
            overflow-x: auto;
        }}
        
        .tab-btn {{
            flex: 1;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px 8px 0 0;
            padding: 0.6rem 0.5rem;
            font-size: var(--fs-base);
            font-weight: 500;
            color: var(--text-light);
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            text-align: center;
        }}
        
        .tab-btn:hover {{
            background: var(--bg);
            color: var(--text);
            transform: translateY(-1px);
        }}
        
        .tab-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
        }}
        
        .tab-content {{
            display: none;
            background: var(--card);
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
            padding: 1.5rem;
            margin-top: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            animation: fadeInUp 0.5s ease-out;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        @keyframes fadeInUp {{
            from {{ 
                opacity: 0; 
                transform: translateY(20px) scale(0.98);
            }}
            to {{ 
                opacity: 1; 
                transform: translateY(0) scale(1);
            }}
        }}

        /* ===== Mobile Responsiveness ===== */
        @media (max-width: 768px) {{
            .container {{
                padding: 12px;
            }}
            .header {{
                padding: 1.25rem;
                border-radius: 8px;
            }}
            .header h1 {{
                font-size: 1.4rem;
            }}
            .session {{
                padding: 1rem;
                border-radius: 8px;
            }}
            .session-title {{
                font-size: 1.2rem;
            }}
            .metric-grid {{
                grid-template-columns: 1fr;
                gap: 0.75rem;
            }}
            .metric-value {{
                font-size: 1.1rem;
            }}
            .comparison-bars {{
                grid-template-columns: 1fr;
                gap: 0.75rem;
            }}
            .comparison-value {{
                font-size: 1.2rem;
            }}
            .tile {{
                padding: 1rem;
                border-radius: 8px;
            }}
            .tile-icon {{
                width: 32px;
                height: 32px;
                font-size: 1rem;
            }}
            .tile-title {{
                font-size: 1rem;
            }}
            .apy-value {{
                font-size: 1.5rem;
            }}
            .range-labels {{
                font-size: 0.65rem;
            }}
            .footer {{
                padding: 1rem;
            }}
            .consent-info {{
                padding: 1rem;
                font-size: 0.85rem;
            }}
            .toc-list {{
                grid-template-columns: 1fr;
            }}
            .health-gauge-container {{
                flex-direction: column;
                align-items: stretch;
            }}
            .health-gauge-ring {{
                margin: 0 auto;
                width: 90px;
                height: 90px;
            }}
            .health-gauge-ring svg {{
                width: 90px;
                height: 90px;
            }}
            .health-gauge-ring .score-number {{
                font-size: 1.4rem;
            }}
            .grid-2, .grid-3, .grid-4, .grid-1a1 {{
                grid-template-columns: 1fr !important;
            }}
            .tab-nav {{
                flex-direction: column;
                gap: 0.25rem;
            }}
            .tab-btn {{
                flex: none;
                padding: 0.5rem 0.75rem;
                font-size: 0.85rem;
                border-radius: 6px;
                text-align: center;
            }}
        }}

        @media (max-width: 380px) {{
            .container {{
                padding: 8px;
            }}
            .header {{
                padding: 1rem;
            }}
            .header h1 {{
                font-size: 1.2rem;
            }}
            .session {{
                padding: 0.75rem;
            }}
            .metric-card {{
                padding: 0.75rem;
            }}
        }}

        /* ===== Responsive Grid Helpers ===== */
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }}
        .grid-3 {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 1rem;
        }}
        .grid-4 {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 1rem;
        }}
        .grid-1a1 {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 1rem;
            align-items: center;
        }}
        /* ===== Export Bar ===== */
        .export-bar {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.75rem;
            margin-bottom: 1rem;
            padding: 0.75rem 1rem;
            background: var(--card);
            border: 1px solid var(--border-light);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
        }}
        .export-bar-label {{
            font-size: var(--fs-sm);
            color: var(--text-light);
            margin-right: auto;
        }}
        .export-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: var(--fs-sm);
            font-weight: 600;
            cursor: pointer;
            border: 1px solid var(--border);
            transition: all 0.2s ease;
            white-space: nowrap;
        }}
        .export-btn:hover {{
            transform: translateY(-1px);
            box-shadow: var(--shadow);
        }}
        .export-btn-primary {{
            background: linear-gradient(135deg, var(--primary), var(--purple));
            color: white;
            border-color: var(--primary);
        }}
        .export-btn-primary:hover {{
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
        }}
        .export-btn-secondary {{
            background: var(--card);
            color: var(--text);
            border-color: var(--border);
        }}
        .export-btn-secondary:hover {{
            background: var(--bg);
            border-color: var(--primary-light);
        }}
        .export-btn-secondary.active {{
            background: linear-gradient(135deg, #ecfdf5, #d1fae5);
            border-color: var(--success);
            color: var(--success);
        }}

        /* ===== Export/Continuous Mode Overrides ===== */
        body.export-mode .tab-nav {{
            display: none !important;
        }}
        body.export-mode .tab-content {{
            display: block !important;
            background: none;
            box-shadow: none;
            border: none;
            padding: 0;
            margin-top: 0;
            backdrop-filter: none;
        }}
        body.export-mode .tab-content + .tab-content {{
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 2px solid var(--border);
        }}
        body.export-mode .collapsible-body {{
            max-height: none !important;
            opacity: 1 !important;
            display: block !important;
        }}
        body.export-mode .collapsible-toggle .chevron {{
            display: none;
        }}

        /* ===== Reduced Motion ===== */
        @media (prefers-reduced-motion: reduce) {{
            .tile, .progress-fill, .gauge-fill, .health-ring-fg, .collapsible-body, .collapsible-toggle .chevron {{
                transition: none !important;
            }}
        }}

        /* ===== Print / Export friendly ===== */
        @media print {{
            body {{
                background: white;
                color: black;
                font-size: 12px;
            }}
            .container {{
                max-width: 100%;
                padding: 0;
            }}
            .header {{
                background: #1e3a5f !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
                padding: 1.5rem;
            }}
            .tile, .session, .metric-card {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .tile:hover {{
                transform: none;
                box-shadow: none;
            }}
            .tile::before {{
                display: none;
            }}
            .toc {{
                display: none;
            }}
            .tab-nav {{
                display: none !important;
            }}
            .tab-content {{
                display: block !important;
                background: none;
                box-shadow: none;
                border: none;
                padding: 0;
                margin-top: 1rem;
                backdrop-filter: none;
            }}
            .collapsible-body {{
                max-height: none !important;
                opacity: 1 !important;
                display: block !important;
            }}
            .collapsible-toggle .chevron {{
                display: none;
            }}
            .copy-btn, .export-bar {{
                display: none !important;
            }}
            .session-title {{
                page-break-after: avoid;
            }}
            .footer {{
                page-break-before: always;
            }}
        }}
    </style>"""
