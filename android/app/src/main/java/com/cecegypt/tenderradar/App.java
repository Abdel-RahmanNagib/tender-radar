package com.cecegypt.tenderradar;

import android.app.ActivityManager;
import android.app.Application;
import android.app.ApplicationExitInfo;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.os.Build;
import android.webkit.WebView;

import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;

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
        if (Build.VERSION.SDK_INT >= 30) {
            new Thread(this::reportLastExit).start();
        }
    }

    /**
     * Android 11+ keeps why the app last stopped. A close without a Java error (the page engine failing, the
     * phone short of memory, a native crash) is sent too, once, so it can be fixed.
     */
    private void reportLastExit() {
        try {
            ActivityManager am = getSystemService(ActivityManager.class);
            List<ApplicationExitInfo> exits = am == null ? null : am.getHistoricalProcessExitReasons(null, 0, 5);
            if (exits == null || exits.isEmpty()) {
                return;
            }
            long seen = prefs().getLong("exit-seen", 0);
            StringBuilder bad = new StringBuilder();
            for (ApplicationExitInfo x : exits) {
                if (x.getTimestamp() <= seen) {
                    continue;
                }
                String desc = String.valueOf(x.getDescription());
                int r = x.getReason();
                // Normal ends (closed by the user, an update, a permission change, frozen in the background) and Java
                // errors (already sent with their full trace) are not reported again.
                boolean expected = r == ApplicationExitInfo.REASON_USER_REQUESTED || r == ApplicationExitInfo.REASON_EXIT_SELF
                        || r == ApplicationExitInfo.REASON_USER_STOPPED || r == ApplicationExitInfo.REASON_PERMISSION_CHANGE
                        || r == ApplicationExitInfo.REASON_CRASH || r == 14 || r == 15 || r == 16
                        || (r == ApplicationExitInfo.REASON_OTHER && desc.matches("(?i).*(remove task|swipe|update).*"));
                if (expected || seen == 0 && r == ApplicationExitInfo.REASON_OTHER) {
                    continue;
                }
                bad.append("\nexit ").append(x.getTimestamp()).append(" reason=").append(r).append(" status=")
                        .append(x.getStatus()).append(" importance=").append(x.getImportance())
                        .append(" pss=").append(x.getPss()).append("kB desc=").append(desc);
                if (r == ApplicationExitInfo.REASON_CRASH_NATIVE || r == ApplicationExitInfo.REASON_ANR) {
                    try (InputStream trace = x.getTraceInputStream()) {
                        if (trace != null) {
                            byte[] head = new byte[1500];
                            int n = trace.read(head);
                            bad.append("\n").append(new String(head, 0, Math.max(n, 0), StandardCharsets.UTF_8));
                        }
                    }
                }
            }
            prefs().edit().putLong("exit-seen", exits.get(0).getTimestamp()).commit();
            if (bad.length() > 0) {
                send(describe() + bad);
            }
        } catch (Exception ignored) {
            // no exit history on this phone
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
