"""
HTML Report CSS Styles
======================

All CSS for the DeFi CLI position analysis report.
Separated from html_generator.py for maintainability.

The status-badge colours are parameterised because they depend
on the position's in-range / out-of-range state.
"""


def build_css(status_bg: str, status_border: str, status_text_color: str) -> str:
    """Return the complete ``<style>`` block for the position report.

    Args:
        status_bg:         Background colour for the status badge.
        status_border:     Border colour for the status badge.
        status_text_color: Text colour for the status badge.
    """
    return f"""    <style>
        :root {{
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #d97706;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --border: #e2e8f0;
            --text: #1e293b;
            --text-light: #64748b;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #1d4ed8 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            text-align: center;
        }}

        .session {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .session-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 1rem;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }}

        .metric-card {{
            padding: 1rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #fafbfc;
            position: relative;
            overflow: hidden;
        }}

        .metric-value {{
            font-size: 1.25rem;
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
            font-size: 0.75rem;
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
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}

        .tile {{
            background: linear-gradient(135deg, white 0%, #f8fafc 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }}

        .tile:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .tile-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
        }}

        .tile-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            margin-right: 1rem;
            font-size: 1.25rem;
        }}

        .tile-title {{
            font-size: 1.1rem;
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
            font-size: 0.875rem;
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
            font-size: 2rem;
            font-weight: 700;
            color: #d97706;
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
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0.5rem 0;
        }}

        .comparison-label {{
            font-size: 0.875rem;
            color: var(--text-light);
        }}

        .strategy-card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            background: #f8fafc;
        }}

        .strategy-details div {{
            margin: 0.5rem 0;
        }}

        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
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
            font-size: 0.95rem;
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.15);
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

        /* ===== Print friendly ===== */
        @media print {{
            body {{
                background: white;
                color: black;
            }}
            .container {{
                max-width: 100%;
            }}
            .tile:hover {{
                transform: none;
                box-shadow: none;
            }}
        }}
    </style>"""
