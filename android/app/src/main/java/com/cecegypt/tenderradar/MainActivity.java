package com.cecegypt.tenderradar;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Shows the tender radar web app full screen and starts the hourly check for new tenders. */
public class MainActivity extends Activity {
    static final String HOST = "abdel-rahmannagib.github.io";
    static final String APP_URL = "https://" + HOST + "/tender-radar/";
    static final String EXTRA_TENDER = "tender";
    private static final String NOTIFY_PERMISSION = "android.permission.POST_NOTIFICATIONS";

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
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportMultipleWindows(false);
        // The web app reads this to know the phone app handles notifications.
        s.setUserAgentString(s.getUserAgentString() + " TenderRadarAndroid/1");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if ("https".equals(u.getScheme()) && HOST.equals(u.getHost())
                        && u.getPath() != null && u.getPath().startsWith("/tender-radar")) {
                    return false;  // pages of the app itself stay inside the app
                }
                openOutside(u);   // official notices, e-mail, phone, WhatsApp: the phone's own apps
                return true;
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

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.getStringExtra(EXTRA_TENDER) != null) {
            web.loadUrl(urlFor(intent));
        }
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
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, u));
        } catch (ActivityNotFoundException e) {
            // nothing on the phone can open this link
        }
    }

    private void askToNotify() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(NOTIFY_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] {NOTIFY_PERMISSION}, 1);
        }
    }
}
