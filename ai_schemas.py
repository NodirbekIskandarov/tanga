"""Gemini uchun JSON sxemalari (oddiy JSON Schema).

Tool/tool_use tushunchasi yo'q: model javobi to'g'ridan-to'g'ri sxemaga mos
JSON. Sxema har chaqiruvda AYNAN bir xil (kesh). Enum qiymatlari config'dan.
Gemini faqat JSON Schema'ning qismini qo'llaydi (string, number, integer,
boolean, object, array, null; enum, required, description, anyOf) va juda
katta/chuqur sxemani rad etishi mumkin — shuning uchun javob baribir
Python'da tekshiriladi (ai.py).
"""

from __future__ import annotations

import copy

import config

RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "niyat": {
            "type": "string",
            "enum": ["yozuv", "savol", "kurs", "tushunarsiz"],
            "description": (
                "'yozuv' — xabarda kirim/chiqim/qarz qayd etilgan. "
                "'savol' — foydalanuvchi o'z moliyasi haqida so'ramoqda "
                "(masalan: bu oy qancha sarfladim). "
                "'kurs' — valyuta kursi yoki konvertatsiya so'ralmoqda "
                "(«400$ so'mda qancha», «1 mln so'm necha dollar», "
                "«dollar kursi qancha»). "
                "'tushunarsiz' — moliyaga aloqasi yo'q yoki summa aniqlanmadi."
            ),
        },
        "kurs_summa": {
            "type": "number",
            "description": (
                "Faqat niyat='kurs' uchun: o'giriladigan summa, aytilmagan "
                "bo'lsa 1. «400$» => 400, «1 mln so'm» => 1000000."
            ),
        },
        "kurs_valyuta": {
            "type": "string",
            "enum": config.SUPPORTED_CURRENCIES,
            "description": (
                "Faqat niyat='kurs' uchun: QAYSI valyutadan o'giriladi. "
                "«400$ so'mda» => 'usd'; «1 mln so'm necha dollar» => 'som'; "
                "«dollar kursi» => 'usd'."
            ),
        },
        "yozuvlar": {
            "type": "array",
            "description": "Xabardagi har bir alohida amaliyot uchun bitta element.",
            "items": {
                "type": "object",
                "properties": {
                    "turi": {
                        "type": "string",
                        "enum": config.KINDS,
                        "description": (
                            "chiqim — pul sarflandi; kirim — pul kelib tushdi; "
                            "qarz_berdim — men birovga qarz berdim; "
                            "qarz_oldim — men birovdan qarz oldim; "
                            "qarz_qaytardim — men O'Z qarzimni qaytardim yoki "
                            "kredit/nasiya to'ladim (pul chiqdi, lekin xarajat "
                            "EMAS); "
                            "qarz_qaytdi — birov menga qarzini qaytardi (pul "
                            "kirdi, lekin daromad EMAS); "
                            "jamgarma — pul shaxsiy jamg'armaga qo'yildi "
                            "(sarflanmadi, o'zida qoldi); "
                            "jamgarma_yechdim — jamg'armadan pul olindi."
                        ),
                    },
                    "summa": {
                        "type": "number",
                        "description": "Musbat son, valyuta birligisiz (masalan 50000).",
                    },
                    "valyuta": {
                        "type": "string",
                        "enum": config.SUPPORTED_CURRENCIES,
                        "description": (
                            "Xabarda \"$\", \"dollar\", \"USD\" kabi ishoralar bo'lsa "
                            "'usd', aks holda har doim 'som'."
                        ),
                    },
                    "kategoriya": {
                        "type": "string",
                        "enum": config.ALL_CATEGORIES,
                        "description": "Turiga mos kategoriya. Qarz uchun har doim 'qarz'.",
                    },
                    "izoh": {
                        "type": "string",
                        "description": (
                            "Qisqa izoh, 1-4 so'z, o'zbek tilida. Masalan: 'tushlik'. "
                            "Qarz uchun sababni yoz agar aytilgan bo'lsa (masalan "
                            "'uy uchun', 'mashina taʼmiri') — shaxs ismini takrorlama, "
                            "sabab aytilmagan bo'lsa 'qarz' deb qo'y."
                        ),
                    },
                    "shaxs": {
                        "type": "string",
                        "description": "Faqat qarz uchun: kimga/kimdan. Aks holda bo'sh qoldir.",
                    },
                    "sana": {
                        "type": "string",
                        "description": (
                            "YYYY-MM-DD formatida. Xabarda sana aytilmagan bo'lsa "
                            "bugungi sanani qo'y."
                        ),
                    },
                    "maqsad": {
                        "type": "string",
                        "description": (
                            "Faqat jamgarma uchun: pul qaysi maqsadga qo'yilgani "
                            "aytilgan bo'lsa, o'sha maqsad nomi 1-3 so'z bilan "
                            "(\"uy uchun 3 mln qo'ydim\" => \"uy\"). Aytilmagan "
                            "bo'lsa bo'sh qoldir."
                        ),
                    },
                    "muddat": {
                        "type": "string",
                        "description": (
                            "Faqat qarz_berdim/qarz_oldim uchun: qarz qachon "
                            "qaytarilishi kerakligi aytilgan bo'lsa, YYYY-MM-DD "
                            "(\"15-oktabrgacha qaytaradi\", \"bir haftada "
                            "beraman\"). Aytilmagan bo'lsa bo'sh qoldir."
                        ),
                    },
                },
                "required": ["turi", "summa", "valyuta", "kategoriya", "izoh", "sana"],
            },
        },
        "izoh_matni": {
            "type": "string",
            "description": (
                "Agar niyat 'tushunarsiz' bo'lsa — foydalanuvchiga o'zbekcha qisqa, "
                "do'stona maslahat: nimani qanday yozish mumkin (masalan "
                "«Summani yozing: taksi 20 ming»). O'zing haqingda («tahlil "
                "qismi», «model», «bot qismi») HECH QACHON gapirma. Aks holda bo'sh."
            ),
        },
    },
    "required": ["niyat", "yozuvlar"],
}


RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "oqildi": {
            "type": "boolean",
            "description": (
                "Rasmda chek bor va hech bo'lmasa bitta mahsulot qatori o'qilgan "
                "bo'lsa true. Rasm chek bo'lmasa yoki umuman o'qib bo'lmasa false."
            ),
        },
        "dokon": {
            "type": "string",
            "description": "Do'kon/tashkilot nomi. Ko'rinmasa bo'sh qoldir.",
        },
        "sana": {
            "type": "string",
            "description": (
                "Chekda yozilgan sana, YYYY-MM-DD formatida. "
                "Chekda sana ko'rinmasa bugungi sanani qo'y."
            ),
        },
        "mahsulotlar": {
            "type": "array",
            "description": (
                "Chekdagi har bir mahsulot qatori uchun bitta element. "
                "Jami/ITOGO/chegirma/QQS kabi yakuniy qatorlarni bu ro'yxatga QO'SHMA."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "nomi": {
                        "type": "string",
                        "description": "Mahsulot nomi chekda yozilganidek.",
                    },
                    "miqdori": {
                        "type": "number",
                        "description": "Soni yoki og'irligi. Ko'rsatilmagan bo'lsa 1.",
                    },
                    "birlik_narxi": {
                        "type": "number",
                        "description": "Bir dona/kg narxi. Ko'rinmasa qo'shma.",
                    },
                    "summa": {
                        "type": "number",
                        "description": (
                            "Shu qator uchun yakuniy summa (miqdor x narx), "
                            "valyuta birligisiz musbat son."
                        ),
                    },
                    "kategoriya": {
                        "type": "string",
                        "enum": config.EXPENSE_CATEGORIES,
                        "description": "Mahsulotga eng mos keladigan kategoriya.",
                    },
                },
                "required": ["nomi", "summa", "kategoriya"],
            },
        },
        "chekdagi_jami": {
            "type": "number",
            "description": (
                "Chekda 'JAMI'/'ITOGO'/'TO'LANDI' deb yozilgan yakuniy summa. "
                "Ko'rinmasa bu maydonni qo'shma."
            ),
        },
        "chegirma": {
            "type": "number",
            "description": "Chegirma/skidka summasi, agar ko'rsatilgan bo'lsa.",
        },
        "valyuta": {
            "type": "string",
            "enum": ["som", "usd"],
            "description": (
                "Chekdagi summalar qaysi valyutada. So'm/sum/UZS yoki "
                "belgisiz => 'som'. $/USD/dollar => 'usd'."
            ),
        },
        "izoh_matni": {
            "type": "string",
            "description": (
                "oqildi=false bo'lsa — nima uchun o'qib bo'lmaganini o'zbekcha "
                "qisqa tushuntir. Aks holda bo'sh."
            ),
        },
    },
    "required": ["oqildi", "mahsulotlar"],
}


# Ovozli xabar: yozuv sxemasi + transkripsiya, ishonch va til. `transkripsiya`
# BIRINCHI turadi: model avval eshitganini yozadi, keyin undan yozuv ajratadi.
_VOICE_EXTRA = {
    "transkripsiya": {
        "type": "string",
        "description": (
            "Foydalanuvchi aytgan gapning so'zma-so'z yozuvi. O'zbekcha — lotin "
            "yozuvida, ruscha — kirillda. Sonlar raqam bilan (\"45 ming\"). "
            "To'ldiruvchi so'zlarsiz. Eshitilmagan bo'lsa bo'sh."
        ),
    },
    "ishonch": {
        "type": "string",
        "enum": ["yuqori", "past"],
        "description": (
            "'past' — summa yoki yo'nalish (kim kimga) aniq eshitilmagan yoki "
            "bir nechta talqin mumkin; aks holda 'yuqori'."
        ),
    },
    "til": {
        "type": "string",
        "enum": ["uz", "ru", "aralash", "boshqa"],
        "description": "Gap tili.",
    },
}


def _voice_schema() -> dict:
    schema = copy.deepcopy(RECORD_SCHEMA)
    props = schema["properties"]
    schema["properties"] = {**_VOICE_EXTRA, **props}
    schema["required"] = ["transkripsiya", "ishonch", *schema["required"]]
    return schema


VOICE_SCHEMA = _voice_schema()
