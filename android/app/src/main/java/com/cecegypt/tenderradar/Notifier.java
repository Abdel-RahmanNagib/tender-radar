package com.cecegypt.tenderradar;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import org.json.JSONObject;

/** Builds the phone notifications (Arabic text, opens the tender inside the app when tapped). */
final class Notifier {
    static final String CHANNEL = "tenders";
    private static final int COLOR = 0xFF0E6D79;

    private Notifier() {
    }

    static void createChannel(Context c) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null) {
            return;
        }
        NotificationChannel ch = new NotificationChannel(CHANNEL, "فرص جديدة", NotificationManager.IMPORTANCE_DEFAULT);
        ch.setDescription("إشعار لكل مناقصة استشارية جديدة مناسبة للمكتب");
        nm.createNotificationChannel(ch);
    }

    static void tender(Context c, JSONObject t) {
        String id = t.optString("id", "");
        if (id.isEmpty()) {
            id = t.optString("uid", "");
        }
        String title = t.optString("title", "");
        String country = t.optString("country", "");
        String level = t.optString("level", "");
        String client = t.optString("client", "");
        String deadline = arabicDate(t.optString("deadline", ""));
        String head = "فرصة جديدة" + (country.isEmpty() ? "" : " – " + country)
                + (level.isEmpty() ? "" : " (" + level + ")");
        StringBuilder body = new StringBuilder(title);
        if (!client.isEmpty()) {
            body.append("\n").append(client);
        }
        if (!deadline.isEmpty()) {
            body.append("\nآخر موعد: ").append(deadline);
        }
        post(c, 1000 + (id.hashCode() & 0x7ffffff), head, title, body.toString(), id);
    }

    static void summary(Context c, int count) {
        String text = "افتح التطبيق لمراجعتها والأوراق المطلوبة لكل فرصة.";
        post(c, 1, "وصلت " + count + " فرص جديدة", text, text, null);
    }

    static void welcome(Context c, int open) {
        String text = "سيصلك إشعار بكل فرصة جديدة مناسبة للمكتب. الفرص المفتوحة الآن: " + open;
        post(c, 2, "رادار المناقصات يعمل", text, text, null);
    }

    static String arabicDate(String iso) {
        if (iso == null || !iso.matches("\\d{4}-\\d{2}-\\d{2}.*")) {
            return iso == null ? "" : iso;
        }
        return iso.substring(8, 10) + "/" + iso.substring(5, 7) + "/" + iso.substring(0, 4);
    }

    private static void post(Context c, int nid, String title, String text, String big, String tenderId) {
        if (Build.VERSION.SDK_INT >= 33
                && c.checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Intent open = new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (tenderId != null) {
            open.putExtra(MainActivity.EXTRA_TENDER, tenderId);
        }
        PendingIntent pi = PendingIntent.getActivity(c, nid, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(c, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setColor(COLOR)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(big))
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build();
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm != null) {
            nm.notify(nid, n);
        }
    }
}
