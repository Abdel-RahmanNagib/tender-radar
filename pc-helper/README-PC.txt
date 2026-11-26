مساعد كمبيوتر المكتب – رادار المناقصات
=====================================

منصة مناقصات قطر والجهاز المركزي للمناقصات بالكويت يرفضان السيرفرات السحابية، لكنهما يفتحان
عادي من شبكة المكتب. هذا المساعد يفحصهما من هذا الكمبيوتر كل ساعة، ويرسل النتائج موقّعة
إلى الفحص السحابي على GitHub، فتظهر في نفس التطبيق وتصل إشعاراتها على نفس القناة.

التثبيت: اضغط مرتين على INSTALL-PC-HELPER.bat (مرة واحدة فقط).
الإيقاف: اضغط مرتين على UNINSTALL-PC-HELPER.bat.

• لا يحتاج كلمة سر أو حساب. يستخدم Python الموجود مع QGIS.
• يعمل فقط والكمبيوتر شغال؛ وأي مناقصة نزلت والجهاز مطفأ تُلتقط في أول فحص بعد تشغيله.
• في كل تشغيل يحدّث كود الفحص من مستودعكم على GitHub (Abdel-RahmanNagib/tender-radar).
• data\pc_key.json هو المفتاح الخاص لهذا الجهاز: لا ترسله لأحد. PUBLIC-KEY.txt مفتاح عام وليس سرياً.
• سجل التشغيل: data\pc-helper.log

Office PC helper (English): scans Qatar Monaqasat and Kuwait CAPT every hour from the office
network and sends signed results to the cloud scan. Install: double-click INSTALL-PC-HELPER.bat.
