# ETH Quant Research & Trading Agent — Antigravity Workspace

هذا المشروع مجلد أبحاث وتجارب لتطوير نظام تحليل ETHUSDT. **ليس بوت تداول حي، وليس استراتيجية مثبتة الربحية**.

## تشغيل سريع

1. فك ضغط `ETH_Quant_Antigravity_Workspace.zip` في مجلد محلي مثل `C:\Projects\ETH-Quant-Agent`.
2. افتح مجلد `ETH_Quant_Antigravity_Workspace` نفسه عبر Antigravity IDE (Open Folder).
3. اقرأ `START_HERE.md`، وافتح محادثة Agent جديدة والصق محتوى `prompts/01_BOOTSTRAP_PROMPT.md`.
4. سيقرأ Antigravity تلقائياً تعليمات `AGENTS.md`؛ يمكنه استخدام Skills الموجودة تحت `.agents/skills/`.
5. شغّل `python -m unittest discover -s tests -v` و `python scripts/check_workspace.py`، ثم نفذ مراحل البحث بالترتيب.

## ماذا يتضمن؟
- `research/backtests/`: جميع تقارير V1 إلى V22، بما فيها الإخفاقات.
- `research/reference/`: ملخص V1→V21 ومنهجية V22، وتسجيل V23 قبل الاطلاع على نتائج الاختبار.
- `research/RESEARCH_LESSONS.md`: ملخص مستخلص من التقارير؛ الملفات الأصلية هي المرجع.
- `artifacts/unverified/`: JSON لإعادة بناء V22 **غير مطابق للأصل وغير مسموح نسبته للأصل**.
- `AGENTS.md`: قواعد بحث دائمة.
- `.agents/skills/`: إجراءات البحث وإعادة الإنتاج والتقييم.
- `prompts/`: برومبت البداية والدورات التالية.
- `docs/`: سياسات فصل العينات والتدقيق ومتطلبات الـSkill.
- `src/eth_research/policy.py`: تنفيذ تمهيدي لبوابة قرار V22، ولا يحتوي على النموذج المدرب.
- `tests/`: اختبارات للبوابة.
- `outputs/`: مكان حفظ النتائج الجديدة؛ لا تغير التقارير الأصلية.

## الحالة العلمية الحالية
- تقرير V22: historical leave-one-period-out = 59.24% (1619/2733)، adaptation = 59.75% (95/159)، Fresh = 59.26% (48/81).
- V23 مسجل للفترة 2025-07-05 حتى 2025-07-11 بتوقيت إسطنبول، **لم يتم تسجيل نتيجته الرسمية**.
- أوزان V22 الأصلية وتعريفات pre-processing الدقيقة غير محفوظة في تقارير المصدر؛ إعادة البناء غير متطابقة بالكامل.
- ملف `ETH_V1_to_V22_Learning_Corpus_and_V23_Methodology.md` الأصلي الذي عُرض سابقاً لم تتوفر نسخته الخام عند تجهيز هذه الحزمة. بديله المتاح ليس بديلاً مطابقاً: `ETH_V1_to_V21_Learning_Corpus_and_V22_Methodology.md`، مع التقرير الكامل V22 وملف V23 pre-registration.

## الحدود
لا تتصل بحساب Binance خاص، ولا تقدم أوامر، ولا تستخدم مفاتيح API؛ هذا workspace لتطوير البحث والمحاكاة فقط. لا يجوز تقديم نجاح التنبؤ بالاتجاه على أنه عائد صافٍ قابل للتحقيق.
