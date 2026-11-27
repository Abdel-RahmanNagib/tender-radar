package com.cecegypt.tenderradar;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.CalendarContract;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.time.LocalDate;
import java.time.ZoneOffset;

/** Shows the tender radar web app full screen and starts the hourly check for new tenders. */
public class MainActivity extends Activity {
    static final String HOST = "abdel-rahmannagib.github.io";
    static final String APP_URL = "https://" + HOST + "/tender-radar/";
    static final String EXTRA_TENDER = "tender";
    private static final String NOTIFY_PERMISSION = "android.permission.POST_NOTIFICATIONS";
    private static final String WEBVIEW_PACKAGE = "com.google.android.webview";
    private static final long DAY = 24L * 60L * 60L * 1000L;

    /** Shown instead of the browser's error page when the phone has no internet and nothing is saved yet. */
    private static final String OFFLINE_PAGE = "<!doctype html><html dir='rtl' lang='ar'><meta charset='utf-8'>"
            + "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<body style='font-family:sans-serif;background:#EEF2F1;color:#142B3B;margin:0;padding:48px 24px;text-align:center'>"
            + "<h2 style='margin:0 0 10px'>لا يوجد اتصال بالإنترنت</h2>"
            + "<p style='margin:0 0 22px;line-height:1.7'>رادار المناقصات يحتاج الإنترنت أول مرة لتحميل الفرص.<br>"
            + "شغّل البيانات أو الواي فاي ثم اضغط «إعادة المحاولة».</p>"
            + "<a href='" + APP_URL + "' style='display:inline-block;background:#142B3B;color:#fff;padding:12px 26px;"
            + "border-radius:10px;text-decoration:none;font-weight:bold'>إعادة المحاولة</a></body></html>";

    private WebView web;
    private int pageCrashes;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.parseColor("#142B3B"));

        // Background work first: a phone that cannot show the page still gets the hourly notifications.
        try {
            Notifier.createChannel(this);
            CheckJob.schedule(this);
            if (!Feed.isInitialized(this)) {
                new Thread(() -> Feed.checkQuietly(getApplicationContext())).start();  // remember today's list
            }
        } catch (RuntimeException e) {
            // notifications are not available on this phone; the app itself still opens
        }
        askToNotify();

        if (!showPage(saved, urlFor(getIntent()))) {
            showProblem("هذا الموبايل لا يستطيع عرض صفحات التطبيق لأن مكوّن «Android System WebView» متوقف أو قديم.",
                    true);
        }
    }

    /** Creates the page view and loads the app. Returns false when the phone has no working WebView. */
    private boolean showPage(Bundle saved, String url) {
        WebView view;
        try {
            view = new WebView(this);
        } catch (RuntimeException e) {
            return false;
        }
        WebSettings s = view.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setSupportMultipleWindows(false);
        // The web app reads this to know the phone app handles notifications.
        s.setUserAgentString(s.getUserAgentString() + " TenderRadarAndroid/3");
        view.addJavascriptInterface(new Bridge(), "TenderRadarApp");
        view.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (isAppPage(u)) {
                    return false;  // pages of the app itself stay inside the app
                }
                openOutside(u);   // official notices, e-mail, phone, WhatsApp: the phone's own apps
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    v.loadDataWithBaseURL(APP_URL, OFFLINE_PAGE, "text/html", "utf-8", null);
                }
            }

            @Override
            public boolean onRenderProcessGone(WebView v, RenderProcessGoneDetail detail) {
                // The page engine stopped (usually the phone ran short of memory). Without this the whole app
                // closes; instead the page is rebuilt, and after repeated failures a clear message is shown.
                if (v != web) {
                    return true;
                }
                web = null;
                setContentView(new View(MainActivity.this));
                v.destroy();
                pageCrashes++;
                if (pageCrashes > 2 || !showPage(null, APP_URL)) {
                    showProblem("توقفت صفحة التطبيق أكثر من مرة على هذا الموبايل. غالباً تحتاج تحديث «Android System WebView» "
                            + "أو إغلاق بعض التطبيقات المفتوحة.", true);
                }
                return true;
            }
        });
        view.setDownloadListener((link, userAgent, disposition, mimeType, length) -> openOutside(Uri.parse(link)));
        web = view;
        setContentView(view);
        if (saved != null) {
            view.restoreState(saved);
        } else {
            view.loadUrl(url);
        }
        return true;
    }

    /** A plain screen (no web page) with the reason and what to do: used only when the page cannot be shown. */
    private void showProblem(String reason, boolean offerUpdate) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(48, 48, 48, 48);
        box.setBackgroundColor(Color.parseColor("#EEF2F1"));

        TextView text = new TextView(this);
        text.setText(reason + "\n\nإشعارات الفرص الجديدة تستمر في الوصول. ويمكنك فتح الرادار في المتصفح:");
        text.setTextColor(Color.parseColor("#142B3B"));
        text.setTextSize(17);
        text.setGravity(Gravity.CENTER);
        box.addView(text);

        if (offerUpdate) {
            box.addView(button("تحديث Android System WebView", v -> {
                if (!startSafely(new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + WEBVIEW_PACKAGE)))) {
                    openOutside(Uri.parse("https://play.google.com/store/apps/details?id=" + WEBVIEW_PACKAGE));
                }
            }));
        }
        box.addView(button("فتح الرادار في المتصفح", v -> openOutside(Uri.parse(APP_URL))));
        box.addView(button("إعادة المحاولة", v -> {
            pageCrashes = 0;
            recreate();
        }));
        setContentView(box);
    }

    private Button button(String label, View.OnClickListener action) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setOnClickListener(action);
        return b;
    }

    static boolean isAppPage(Uri u) {
        return "https".equals(u.getScheme()) && HOST.equals(u.getHost())
                && u.getPath() != null && u.getPath().startsWith("/tender-radar");
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (web != null && intent.getStringExtra(EXTRA_TENDER) != null) {
            web.loadUrl(urlFor(intent));
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) {
            web.onResume();  // the page sees it is visible again and fetches the newest list
        }
    }

    @Override
    protected void onPause() {
        if (web != null) {
            web.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (web != null) {
            web.saveState(out);
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    static String urlFor(Intent intent) {
        String id = intent == null ? null : intent.getStringExtra(EXTRA_TENDER);
        return id == null || id.isEmpty() ? APP_URL : APP_URL + "#t-" + Uri.encode(id);
    }

    private void openOutside(Uri u) {
        runOnUiThread(() -> startSafely(new Intent(Intent.ACTION_VIEW, u)));
    }

    private boolean startSafely(Intent i) {
        try {
            startActivity(i);
            return true;
        } catch (ActivityNotFoundException | SecurityException e) {
            return false;  // nothing on the phone can open this
        }
    }

    private void askToNotify() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(NOTIFY_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] {NOTIFY_PERMISSION}, 1);
        }
    }

    /** What the web app can ask the phone to do (only pages of the app are ever loaded here). */
    public final class Bridge {
        @JavascriptInterface
        public void share(String title, String text, String url) {
            Intent send = new Intent(Intent.ACTION_SEND)
                    .setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, title)
                    .putExtra(Intent.EXTRA_TEXT, text + "\n" + url);
            runOnUiThread(() -> startSafely(Intent.createChooser(send, "مشاركة الفرصة")));
        }

        /** Opens the phone's calendar with an all-day event on the deadline (date as yyyy-mm-dd). */
        @JavascriptInterface
        public void calendar(String title, String date, String notes) {
            long begin;
            try {
                begin = LocalDate.parse(date.substring(0, 10)).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli();
            } catch (RuntimeException e) {
                return;
            }
            Intent add = new Intent(Intent.ACTION_INSERT)
                    .setData(CalendarContract.Events.CONTENT_URI)
                    .putExtra(CalendarContract.Events.TITLE, title)
                    .putExtra(CalendarContract.Events.DESCRIPTION, notes)
                    .putExtra(CalendarContract.EXTRA_EVENT_ALL_DAY, true)
                    .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, begin)
                    .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, begin + DAY);
            runOnUiThread(() -> startSafely(add));
        }

        @JavascriptInterface
        public boolean backgroundAllowed() {
            PowerManager pm = getSystemService(PowerManager.class);
            return pm == null || pm.isIgnoringBatteryOptimizations(getPackageName());
        }

        /** Asks the phone (one system question) to let the hourly check run even on battery saver. */
        @JavascriptInterface
        public void allowBackground() {
            runOnUiThread(() -> {
                if (!startSafely(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        Uri.parse("package:" + getPackageName())))) {
                    startSafely(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                }
            });
        }
    }
}
