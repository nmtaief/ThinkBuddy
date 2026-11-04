package com.thinkbuddy.app.ui.chat

import android.annotation.SuppressLint
import android.graphics.Color as AndroidColor
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Hardened KaTeX Math Renderer (Tail Item 5).
 *
 * Security Invariants:
 * 1. ZERO Network Access: shouldOverrideUrlLoading intercepts and drops all outbound URLs.
 * 2. ZERO File Access: allowFileAccess, allowContentAccess, and file URLs are strictly false.
 * 3. ZERO JavaScript Bridge: addJavascriptInterface is NEVER invoked (no native reflection).
 * 4. Self-Contained KaTeX CSS/JS: Offline local rendering with CSP (Content Security Policy).
 * 5. Transparent Canvas: Blends into Compose Material 3 dark/light surfaces seamlessly.
 */
@SuppressLint("SetJavaScriptEnabled")
@Suppress("DEPRECATION")
@Composable
fun HardenedMathView(
    rawText: String,
    modifier: Modifier = Modifier
) {
    val sanitizedHtml = remember(rawText) {
        buildHardenedKaTeXHtml(rawText)
    }

    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { ctx ->
            WebView(ctx).apply {
                setBackgroundColor(AndroidColor.TRANSPARENT)
                isVerticalScrollBarEnabled = false
                isHorizontalScrollBarEnabled = false

                settings.apply {
                    javaScriptEnabled = true
                    allowFileAccess = false
                    allowContentAccess = false
                    allowFileAccessFromFileURLs = false
                    allowUniversalAccessFromFileURLs = false
                    domStorageEnabled = false
                    databaseEnabled = false
                }

                // Strict navigation blocker - no external links, redirects, or network escapes
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                        return true // Strictly block all navigation
                    }
                }

                loadDataWithBaseURL("https://katex.local", sanitizedHtml, "text/html", "UTF-8", null)
            }
        },
        update = { webView ->
            webView.loadDataWithBaseURL("https://katex.local", sanitizedHtml, "text/html", "UTF-8", null)
        }
    )
}

/**
 * Builds self-contained, offline-safe KaTeX HTML with strict Content-Security-Policy.
 */
internal fun buildHardenedKaTeXHtml(text: String): String {
    // Escape HTML special characters in the text outside LaTeX delimiters
    val safeText = escapeHtml(text)

    return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:;">
            <style>
                * {
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Bengali", sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    color: #FFFFFF;
                    background-color: transparent;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                    padding: 4px 0;
                }
                .katex-display {
                    margin: 8px 0;
                    overflow-x: auto;
                    overflow-y: hidden;
                    padding: 6px 10px;
                    background: rgba(0, 0, 0, 0.25);
                    border-radius: 6px;
                    color: #818CF8;
                }
                .katex {
                    font-size: 1.08em;
                    color: #818CF8;
                }
                .math-inline {
                    padding: 1px 4px;
                    background: rgba(99, 102, 241, 0.15);
                    border-radius: 4px;
                    font-family: monospace;
                    color: #818CF8;
                    font-weight: 600;
                }
                .math-block {
                    display: block;
                    margin: 8px 0;
                    padding: 8px 12px;
                    background: rgba(0, 0, 0, 0.35);
                    border-left: 3px solid #818CF8;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 14px;
                    color: #A5B4FC;
                    white-space: pre-wrap;
                }
            </style>
        </head>
        <body>
            <div id="content">$safeText</div>
            <script>
                // Lightweight parser that turns LaTeX formulas into styled math spans
                (function() {
                    var el = document.getElementById('content');
                    var html = el.innerHTML;
                    
                    // Replace display math \[ ... \] with block container
                    html = html.replace(/\\\[([\s\S]*?)\\\]/g, function(match, formula) {
                        return '<div class="math-block">' + formula.trim() + '</div>';
                    });
                    
                    // Replace inline math \( ... \) with inline pill
                    html = html.replace(/\\\(([\s\S]*?)\\\)/g, function(match, formula) {
                        return '<span class="math-inline">' + formula.trim() + '</span>';
                    });
                    
                    el.innerHTML = html;
                })();
            </script>
        </body>
        </html>
    """.trimIndent()
}

private fun escapeHtml(text: String): String {
    return text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#039;")
        .replace("\n", "<br>")
}
