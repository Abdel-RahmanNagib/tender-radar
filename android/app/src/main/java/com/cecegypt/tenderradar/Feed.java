package com.cecegypt.tenderradar;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Reads the small list of open tenders that the hourly scan publishes and notifies the new ones. */
final class Feed {
    private static final String FEED_URL = MainActivity.APP_URL + "data/feed.json";
    private static final String PREFS = "radar";
    private static final int MAX_SINGLE = 6;   // more than this at once: one summary notification
    private static final int MAX_REMEMBERED = 800;

    private Feed() {
    }

    static boolean isInitialized(Context c) {
        return prefs(c).getBoolean("initialized", false);
    }

    static void checkQuietly(Context c) {
        try {
            check(c);
        } catch (Exception e) {
            // offline: the hourly job will initialise the list later
        }
    }

    static synchronized void check(Context c) throws Exception {
        JSONObject root = new JSONObject(download(FEED_URL + "?t=" + System.currentTimeMillis()));
        JSONArray items = root.optJSONArray("items");
        if (items == null) {
            return;
        }
        SharedPreferences p = prefs(c);
        Set<String> seen = new HashSet<>(p.getStringSet("seen", Collections.<String>emptySet()));
        boolean first = !p.getBoolean("initialized", false);
        Set<String> listed = new HashSet<>();
        List<JSONObject> fresh = new ArrayList<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject t = items.optJSONObject(i);
            String uid = t == null ? "" : t.optString("uid", "");
            if (uid.isEmpty()) {
                continue;
            }
            listed.add(uid);
            if (!seen.contains(uid)) {
                fresh.add(t);
            }
        }
        if (first) {
            Notifier.welcome(c, root.optInt("count", listed.size()));
        } else if (!fresh.isEmpty()) {
            for (int i = 0; i < Math.min(fresh.size(), MAX_SINGLE); i++) {
                Notifier.tender(c, fresh.get(i));
            }
            if (fresh.size() > MAX_SINGLE) {
                Notifier.summary(c, fresh.size());
            }
        }
        Set<String> keep = new HashSet<>(listed);
        if (seen.size() + listed.size() < MAX_REMEMBERED) {
            keep.addAll(seen);  // a tender that leaves the list and comes back is not announced twice
        }
        p.edit()
                .putStringSet("seen", keep)
                .putBoolean("initialized", true)
                .putLong("checked", System.currentTimeMillis())
                .apply();
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static String download(String address) throws Exception {
        HttpURLConnection con = (HttpURLConnection) new URL(address).openConnection();
        con.setConnectTimeout(20000);
        con.setReadTimeout(30000);
        con.setRequestProperty("Accept", "application/json");
        con.setRequestProperty("Cache-Control", "no-cache");
        try {
            if (con.getResponseCode() != 200) {
                throw new IllegalStateException("HTTP " + con.getResponseCode());
            }
            try (InputStream in = con.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
                return new String(out.toByteArray(), StandardCharsets.UTF_8);
            }
        } finally {
            con.disconnect();
        }
    }
}
