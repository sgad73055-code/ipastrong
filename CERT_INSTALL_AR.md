# التثبيت المباشر — دليل التشغيل

## كيف يعمل
`certs/registry.json` ← يقرأه المتصفح ← لكل خيار طلب مستقل إلى `/api/cert-status` ← يفحص manifest ثم أول 4 بايتات من IPA ← يظهر زر «تثبيت» (`itms-services`).

القسم **مخفي تماماً** ما دام السجل فارغاً.

## قبل إضافة أي خيار
- يجب أن يكون ملف IPA **موقّعاً مسبقاً**. ملف manifest لا يوقّع التطبيق، وروابط الكتالوج الحالية لا تصير قابلة للتثبيت لمجرد إنشاء manifest لها.
- **Ad Hoc:** يتثبت فقط على الأجهزة التي UDID الخاص بها داخل ملف التزويد (provisioning profile).
- **Enterprise:** رخصة Apple تقصره على موظفي المؤسسة المالكة. لا تستخدمه لتوزيع عام على المشتركين.
- لا تستخدم شهادة أو manifest من طرف آخر بدون إذن منه، ولا تنشر تطبيقات لا تملك حق توزيعها.
- لا ترفع `.p12` أو `.mobileprovision` أو كلمة مرور. السجل عام، فلا تضع فيه أي سر.

## الخطوات
1. ارفع IPA الموقّع على استضافة HTTPS تملكها (ليس على Pages؛ الحد 25 MiB للملف).
2. أنشئ manifest:

       python3 tools/make_manifest.py --ipa-url https://YOUR-HOST/app.ipa --bundle-id com.example.app --version 1.0 --title "اسم التطبيق" --out certs/manifests/app.plist

   القيم يجب أن تطابق التطبيق الموقّع (انتبه: التوقيع قد يغيّر الـBundle ID).
3. أضف داخل `certificates` في `certs/registry.json` عنصراً بهذا الشكل (القيم التي بين <> تستبدلها):

```json
{
  "id": "<cert-1>",
  "label": "<اسم يظهر للمستخدم>",
  "type": "adhoc",
  "enabled": true,
  "expiresAt": "<YYYY-MM-DD>",
  "authorization": { "grantedBy": "<مالك الإذن>", "reference": "<مرجع الإذن، بدون أسرار>" },
  "installs": [
    {
      "id": "<app-1>",
      "name": "<اسم التطبيق>",
      "version": "<1.0>",
      "bundleIdentifier": "<com.example.app>",
      "iconURL": "<https://...png>",
      "manifestURL": "https://ipastrong.pages.dev/certs/manifests/app.plist",
      "catalogDownloadURL": "<اختياري: رابط الكتالوج المطابق حرفياً ليظهر الزر داخل نافذة التفاصيل>"
    }
  ]
}
```

`catalogDownloadURL` يربط بين الإدخالين فقط ولا يغيّر الكتالوج. اربطه فقط إذا كانت النسخة الموقّعة هي نفس نسخة الكتالوج.

لإيقاف شهادة (مثلاً بعد إلغائها من Apple) غيّر `enabled` إلى `false` ثم انشر.

## النشر على Cloudflare Pages
- استخدم ربط Git (Build command فارغ، Output directory هو `/` جذر المستودع) أو `npx wrangler pages deploy .`.
- **الرفع بالسحب والإفلات لا يشغّل مجلد `functions`**، وعندها تبقى الخيارات بحالة «تعذّر الفحص».
- GitHub Pages لا يشغّل Functions أيضاً.
- بعد النشر افتح `/api/cert-status?cert=x&install=y`؛ المتوقع JSON فيه `unknown_entry`.

## الاختبار
    node --test tests/cert-install.test.mjs

## معنى نجاح الفحص
الروابط تعمل، وmanifest سليم، والـBundle ID فيه يطابق السجل، والملف يبدأ بتوقيع ZIP. الفحص **لا يتحقق** من إلغاء الشهادة، ولا من صحة التوقيع، ولا من شمول جهاز المستخدم. تاريخ الانتهاء يؤخذ مما تكتبه أنت في السجل. نتيجة النجاح تُخزّن 5 دقائق والفشل دقيقة.

## التراجع
احذف سطري `cert-install` من `index.html`.
