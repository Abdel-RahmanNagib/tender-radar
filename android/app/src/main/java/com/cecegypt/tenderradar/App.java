package com.cecegypt.tenderradar;

import android.app.Application;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.os.Build;
import android.webkit.WebView;

import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Starts before any screen. If the app ever closes because of an error, the reason (Android version, phone
 * model, app version and the error itself, nothing personal) is kept and sent once at the next start, so the
 * problem can be found and fixed without access to the phone.
 */
public class App extends Application {
    static final String CRASH_REPORTS = "https://ntfy.sh/tender-radar-app-crash-7f3k2q9d";
    private static final String PREFS = "crash";

    @Override
    public void onCreate() {
        super.onCreate();
        Thread.UncaughtExceptionHandler android = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            try {
                StringWriter trace = new StringWriter();
                error.printStackTrace(new PrintWriter(trace));
                String report = describe() + "\nthread: " + thread.getName() + "\n" + trace;
                prefs().edit().putString("report", report).commit();
                // Send it now, while the app is still alive (a phone where it closes at every start would
                // otherwise never get the chance). Wait at most 3.5 seconds.
                Thread sender = new Thread(() -> send(report));
                sender.start();
                sender.join(3500);
            } catch (Throwable ignored) {
                // never let the report itself hide the original error
            }
            if (android != null) {
                android.uncaughtException(thread, error);
            }
        });
        String report = prefs().getString("report", null);
        if (report != null) {
            new Thread(() -> send(report)).start();
        }
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    String describe() {
        StringBuilder s = new StringBuilder("Tender Radar app");
        try {
            PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0);
            s.append(' ').append(p.versionName);
        } catch (Exception ignored) {
            // version unknown
        }
        s.append(" | Android ").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(')')
                .append(" | ").append(Build.MANUFACTURER).append(' ').append(Build.MODEL);
        try {
            PackageInfo w = WebView.getCurrentWebViewPackage();
            s.append(" | WebView ").append(w == null ? "missing" : w.packageName + " " + w.versionName);
        } catch (Throwable ignored) {
            // WebView unavailable
        }
        return s.toString();
    }

    private void send(String report) {
        try {
            HttpURLConnection con = (HttpURLConnection) new URL(CRASH_REPORTS).openConnection();
            con.setConnectTimeout(15000);
            con.setReadTimeout(15000);
            con.setRequestMethod("POST");
            con.setDoOutput(true);
            con.setRequestProperty("Title", "Tender Radar app closed");
            byte[] body = report.getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = con.getOutputStream()) {
                out.write(body, 0, Math.min(body.length, 3900));
            }
            if (con.getResponseCode() < 300) {
                prefs().edit().remove("report").commit();
            }
            con.disconnect();
        } catch (Exception ignored) {
            // no internet now: try again at the next start
        }
    }
}
