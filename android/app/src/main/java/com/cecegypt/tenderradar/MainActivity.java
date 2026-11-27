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
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.time.LocalDate;
import java.time.ZoneOffset;

/** Shows the tender radar web app full screen and starts the hourly check for new tenders. */
public class MainActivity extends Activity {
    static final String HOST = "abdel-rahmannagib.github.io";
    static final String APP_URL = "https://" + HOST + "/tender-radar/";
    static final String EXTRA_TENDER = "tender";
    private static final String NOTIFY_PERMISSION = "android.permission.POST_NOTIFICATIONS";
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

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.parseColor("#142B3B"));
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setSupportMultipleWindows(false);
        // The web app reads this to know the phone app handles notifications.
        s.setUserAgentString(s.getUserAgentString() + " TenderRadarAndroid/2");
        web.addJavascriptInterface(new Bridge(), "TenderRadarApp");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (isAppPage(u)) {
                    return false;  // pages of the app itself stay inside the app
                }
                openOutside(u);   // official notices, e-mail, phone, WhatsApp: the phone's own apps
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    view.loadDataWithBaseURL(APP_URL, OFFLINE_PAGE, "text/html", "utf-8", null);
                }
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mimeType, length) -> openOutside(Uri.parse(url)));

        Notifier.createChannel(this);
        CheckJob.schedule(this);
        if (!Feed.isInitialized(this)) {
            new Thread(() -> Feed.checkQuietly(getApplicationContext())).start();  // remember today's list
        }
        askToNotify();

        if (saved != null) {
            web.restoreState(saved);
        } else {
            web.loadUrl(urlFor(getIntent()));
        }
    }

    static boolean isAppPage(Uri u) {
        return "https".equals(u.getScheme()) && HOST.equals(u.getHost())
                && u.getPath() != null && u.getPath().startsWith("/tender-radar");
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.getStringExtra(EXTRA_TENDER) != null) {
            web.loadUrl(urlFor(intent));
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();  // the page sees it is visible again and fetches the newest list
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
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
        start(new Intent(Intent.ACTION_VIEW, u));
    }

    private void start(Intent i) {
        runOnUiThread(() -> {
            try {
                startActivity(i);
            } catch (ActivityNotFoundException e) {
                // nothing on the phone can open this
            }
        });
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
            start(Intent.createChooser(send, "مشاركة الفرصة"));
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
            start(new Intent(Intent.ACTION_INSERT)
                    .setData(CalendarContract.Events.CONTENT_URI)
                    .putExtra(CalendarContract.Events.TITLE, title)
                    .putExtra(CalendarContract.Events.DESCRIPTION, notes)
                    .putExtra(CalendarContract.EXTRA_EVENT_ALL_DAY, true)
                    .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, begin)
                    .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, begin + DAY));
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
                try {
                    startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                            Uri.parse("package:" + getPackageName())));
                } catch (ActivityNotFoundException e) {
                    try {
                        startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                    } catch (ActivityNotFoundException ignored) {
                        // this phone has no such setting
                    }
                }
            });
        }
    }
}
