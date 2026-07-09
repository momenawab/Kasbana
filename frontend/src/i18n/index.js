import { createContext, useContext } from 'react'
import { ONE_LINER, ONE_LINER_AR, CONTACT_EMAIL } from '../config.js'

// ─────────────────────────────────────────────────────────────────────────────
// Two full language versions of the site. English lives at "/"; Arabic lives at
// "/ar". All user-facing copy is keyed here so each page renders in ONE language.
// ─────────────────────────────────────────────────────────────────────────────

export const LANGS = ['en', 'ar']

// Maps a logical page → its path in each language.
export const PAGE_PATHS = {
  home: { en: '/', ar: '/ar' },
  support: { en: '/support', ar: '/ar/support' },
  privacy: { en: '/privacy', ar: '/ar/privacy' },
  getStarted: { en: '/get-started', ar: '/ar/get-started' },
}

export const translations = {
  en: {
    dir: 'ltr',
    nav: {
      home: 'Home',
      support: 'Support',
      privacy: 'Privacy',
      login: 'Log in',
      getStarted: 'Get started',
    },
    switchLabel: 'العربية', // shown on the EN site to jump to Arabic
    switchTo: 'ar',
    home: {
      pill: 'Coming soon',
      title: 'Turn every purchase into',
      titleAccent: 'lasting loyalty.',
      lead: "Create beautiful, interactive digital loyalty cards that live directly inside your customers' Apple Wallet and Google Wallet — no app download required.",
      ctaPrimary: 'Get started free',
      contactCta: 'Contact us',
      privacyCta: 'Privacy',
      socialProof:
        'Launching soon for cafés, restaurants, salons & shops across Egypt.',
      sectionTitle: "What we're building",
      sectionSub:
        'A digital loyalty and rewards platform that businesses set up in minutes — and customers never have to download.',
      features: [
        {
          icon: 'wallet',
          title: 'In your wallet, no app',
          body: 'Cards live in Apple Wallet and Google Wallet. Nothing to download, nothing to install — customers just tap “Add”.',
        },
        {
          icon: 'loyalty',
          title: 'Stamps & rewards',
          body: 'Run stamp cards and points programs, hand out rewards straight from the dashboard.',
        },
        {
          icon: 'bolt',
          title: 'Instant updates',
          body: 'Push changes to a card the moment a customer earns a stamp — right on their lock screen.',
        },
        {
          icon: 'public',
          title: 'Arabic-first, built for Egypt',
          body: 'Designed Arabic-first for cafés, restaurants, salons, gyms, and shops across Egypt and the region.',
        },
      ],
      // Labels for the illustrative product preview beside the hero (decorative).
      preview: {
        liveLabel: 'Preview',
        cardName: 'Bloom Café',
        cardTier: 'Loyalty card',
        stampsLabel: 'Rewards progress',
        stampsCount: '9 / 10 stamps',
        rewardUnlocked: 'Reward unlocked',
        rewardItem: 'Free artisan coffee',
        activityName: 'Sarah',
        activity: 'just earned a stamp',
      },
    },
    support: {
      pill: "We're here to help",
      title: "Let's",
      titleAccent: 'talk.',
      lead: "Questions about setup, pricing, or anything else? Send us a message and we'll get back to you by email.",
      points: [
        { icon: 'schedule', text: 'We reply by email, usually within a day' },
        { icon: 'support_agent', text: 'Real people — ask us anything about Stampn' },
      ],
      emailLabel: 'Prefer email? Reach us at',
      cardTitle: 'Send a message',
      cardSub: "We'll reply to your email as soon as we can.",
      labels: {
        name: 'Name',
        email: 'Email',
        subject: 'Subject',
        message: 'Message',
      },
      submit: 'Send message',
      submitting: 'Sending…',
      errors: {
        name: 'Please enter your name.',
        email: 'Please enter your email.',
        emailInvalid: 'Please enter a valid email address.',
        subject: 'Please enter a subject.',
        message: 'Please enter a message.',
        fix: 'Please fix the highlighted fields and try again.',
        network:
          'We could not reach the server. Check your connection and try again.',
        generic: 'Something went wrong sending your message. Please try again.',
      },
      success: {
        title: 'Message sent! 📨',
        body: "Thanks! Your message is on its way — we'll reply by email.",
        note: "We'll be in touch shortly.",
        back: 'Back to home',
      },
    },
    getStarted: {
      pill: 'Early access · limited spots',
      title: 'Reserve your',
      titleAccent: 'spot.',
      lead: "We're onboarding a first wave of businesses. Leave your details and we'll personally set up your loyalty program — then reach out within one day.",
      benefits: [
        'Free white-glove setup of your first loyalty card',
        'Priority onboarding before public launch',
        'Founding-member pricing, locked in for good',
      ],
      socialProof: 'Cafés, restaurants & shops are already on the list.',
      cardTitle: 'Join the waitlist',
      cardSub: 'Takes 30 seconds — no app, no credit card.',
      labels: {
        name: 'Your name',
        email: 'Email',
        phone: 'Phone number',
        business: 'Business name',
      },
      submit: 'Join the waitlist',
      submitting: 'Reserving your spot…',
      note: "We'll only use these details to set up your account and reach out.",
      errors: {
        name: 'Please enter your name.',
        email: 'Please enter your email.',
        emailInvalid: 'Please enter a valid email address.',
        phone: 'Please enter your phone number.',
        business: 'Please enter your business name.',
        fix: 'Please fix the highlighted fields and try again.',
        network:
          'We could not reach the server. Check your connection and try again.',
        generic: 'Something went wrong. Please try again.',
      },
      success: {
        title: "You're on the list! 🎉",
        body: "We've saved your spot. Our team will reach out within one day to get your loyalty program set up.",
        note: "Keep an eye on your inbox — we'll be in touch very soon.",
        back: 'Back to home',
      },
    },
    privacy: {
      title: 'Privacy Policy',
      updated: 'Last updated: 28 June 2026',
      intro:
        'This policy explains what information Stampn collects through this website and how we use it. Stampn is a digital loyalty and rewards platform; this site is currently a pre-launch “coming soon” page with a contact form.',
      collectH: 'What we collect',
      collectP: 'When you submit the support form, we collect the information you choose to send us:',
      collectList: ['Your name', 'Your email address', 'The subject and message you write'],
      collectNote:
        'We do not collect this information any other way on this site, and we do not use tracking or advertising cookies.',
      useH: 'How we use it',
      useP: 'We use the information you submit for one purpose only: to read your message and reply to you by email. We do not sell it, rent it, or share it with third parties for marketing. Your message is delivered to our team by our form-handling provider purely so we can receive and respond to it.',
      keepH: 'How long we keep it',
      keepP: 'We keep your message only as long as needed to handle your request and our correspondence with you. After that, we delete it.',
      deleteH: 'Requesting deletion',
      deleteP1: 'You can ask us to delete the information you sent at any time. Email',
      deleteP2:
        'from the address you used and ask us to delete your data, and we will remove it from our inbox and records.',
      contactH: 'Contact',
      contactP: 'For any privacy question, contact us at',
    },
    footer: {
      rights: 'All rights reserved.',
      tagline: 'Built for the future of loyalty.',
    },
    notFound: {
      title: '404',
      lead: "We couldn't find that page.",
      cta: 'Back home',
    },
    seo: {
      home: {
        title: "Stampn — Digital loyalty cards in your customers' wallet",
        description:
          'Stampn is a digital loyalty and rewards platform for cafés, restaurants, salons, gyms, and shops. Customers add stamp and points cards to Apple Wallet and Google Wallet — no app needed. Built for Egypt, Arabic-first.',
      },
      support: {
        title: 'Support — Stampn',
        description: "Questions about Stampn? Send us a message and we'll reply by email.",
      },
      getStarted: {
        title: 'Get started — Stampn',
        description:
          "Leave your details and the Stampn team will contact you within one day to set up your digital loyalty program.",
      },
      privacy: {
        title: 'Privacy Policy — Stampn',
        description: 'How Stampn handles the information you submit through our contact form.',
      },
    },
  },

  ar: {
    dir: 'rtl',
    nav: {
      home: 'الرئيسية',
      support: 'الدعم',
      privacy: 'الخصوصية',
      login: 'تسجيل الدخول',
      getStarted: 'ابدأ الآن',
    },
    switchLabel: 'English', // shown on the AR site to jump to English
    switchTo: 'en',
    home: {
      pill: 'قريبًا',
      title: 'حوّل كل عملية شراء إلى',
      titleAccent: 'ولاء دايم.',
      lead: 'اعمل كروت ولاء رقمية تفاعلية وشيك بتعيش جوّه Apple Wallet و Google Wallet عند عملائك — من غير ما حد يحمّل أي تطبيق.',
      ctaPrimary: 'ابدأ مجانًا',
      contactCta: 'تواصل معنا',
      privacyCta: 'الخصوصية',
      socialProof:
        'بنطلق قريبًا للكافيهات والمطاعم والصالونات والمحلات في مصر.',
      sectionTitle: 'اللي بنبنيه',
      sectionSub:
        'منصّة ولاء ومكافآت رقمية بتتظبط في دقايق — والعميل مش محتاج يحمّل أي حاجة.',
      features: [
        {
          icon: 'wallet',
          title: 'في محفظتك، من غير تطبيق',
          body: 'الكروت بتعيش في Apple Wallet و Google Wallet. مفيش حاجة تتحمّل ولا تتثبّت — العميل بيضغط «إضافة» وبس.',
        },
        {
          icon: 'loyalty',
          title: 'أختام ومكافآت',
          body: 'اعمل كروت أختام وبرامج نقاط، ووزّع مكافآت على طول من لوحة التحكم.',
        },
        {
          icon: 'bolt',
          title: 'تحديثات فورية',
          body: 'التغييرات بتوصل للكارت في نفس اللحظة اللي العميل بياخد فيها ختم — على شاشة القفل مباشرة.',
        },
        {
          icon: 'public',
          title: 'بالعربي الأول، اتعمل لمصر',
          body: 'مصمّم بالعربي الأول للكافيهات والمطاعم والصالونات والجيمات والمحلات في مصر والمنطقة.',
        },
      ],
      // نصوص المعاينة التوضيحية جنب الهيرو (زخرفية).
      preview: {
        liveLabel: 'معاينة',
        cardName: 'كافيه بلوم',
        cardTier: 'كارت ولاء',
        stampsLabel: 'تقدّم المكافآت',
        stampsCount: '٩ / ١٠ أختام',
        rewardUnlocked: 'مكافأة اتفتحت',
        rewardItem: 'قهوة مجانية',
        activityName: 'سارة',
        activity: 'أخدت ختم دلوقتي',
      },
    },
    support: {
      pill: 'احنا هنا نساعدك',
      title: 'خلينا',
      titleAccent: 'نتكلم.',
      lead: 'عندك سؤال عن التفعيل أو الأسعار أو أي حاجة؟ ابعتلنا رسالة وهنرد عليك على الإيميل.',
      points: [
        { icon: 'schedule', text: 'بنرد بالإيميل، عادة خلال يوم' },
        { icon: 'support_agent', text: 'ناس حقيقية — اسألنا أي حاجة عن Stampn' },
      ],
      emailLabel: 'تحب الإيميل؟ راسلنا على',
      cardTitle: 'ابعتلنا رسالة',
      cardSub: 'هنرد عليك على إيميلك في أقرب وقت.',
      labels: {
        name: 'الاسم',
        email: 'البريد الإلكتروني',
        subject: 'الموضوع',
        message: 'الرسالة',
      },
      submit: 'إرسال',
      submitting: 'جاري الإرسال…',
      errors: {
        name: 'من فضلك اكتب اسمك.',
        email: 'من فضلك اكتب بريدك الإلكتروني.',
        emailInvalid: 'من فضلك اكتب بريد إلكتروني صحيح.',
        subject: 'من فضلك اكتب الموضوع.',
        message: 'من فضلك اكتب رسالتك.',
        fix: 'من فضلك صحّح الحقول المظللة وحاول تاني.',
        network: 'مقدرناش نوصل للسيرفر. اتأكد من اتصالك وحاول تاني.',
        generic: 'حصلت مشكلة في إرسال رسالتك. من فضلك حاول تاني.',
      },
      success: {
        title: 'اتبعتت! 📨',
        body: 'تمام! وصلتنا رسالتك وهنرد عليك على الإيميل.',
        note: 'هنتواصل معاك قريب.',
        back: 'الرجوع للرئيسية',
      },
    },
    getStarted: {
      pill: 'وصول مبكر · أماكن محدودة',
      title: 'احجز',
      titleAccent: 'مكانك.',
      lead: 'إحنا بنضم أول مجموعة من النشاطات. سيب بياناتك وإحنا هنجهّزلك برنامج الولاء بنفسنا — ونتواصل معاك خلال يوم واحد.',
      benefits: [
        'تجهيز كامل لأول كارت ولاء ليك — علينا',
        'أولوية في التفعيل قبل الإطلاق الرسمي',
        'سعر المؤسسين محجوز ليك للأبد',
      ],
      socialProof: 'كافيهات ومطاعم ومحلات موجودة على القائمة بالفعل.',
      cardTitle: 'انضم لقائمة الانتظار',
      cardSub: 'بياخد 30 ثانية — من غير تطبيق ولا كارت ائتمان.',
      labels: {
        name: 'اسمك',
        email: 'البريد الإلكتروني',
        phone: 'رقم الموبايل',
        business: 'اسم النشاط التجاري',
      },
      submit: 'انضم لقائمة الانتظار',
      submitting: 'بنحجز مكانك…',
      note: 'هنستخدم بياناتك بس عشان نجهّز حسابك ونتواصل معاك.',
      errors: {
        name: 'من فضلك اكتب اسمك.',
        email: 'من فضلك اكتب بريدك الإلكتروني.',
        emailInvalid: 'من فضلك اكتب بريد إلكتروني صحيح.',
        phone: 'من فضلك اكتب رقم موبايلك.',
        business: 'من فضلك اكتب اسم نشاطك التجاري.',
        fix: 'من فضلك صحّح الحقول المظللة وحاول تاني.',
        network: 'مقدرناش نوصل للسيرفر. اتأكد من اتصالك وحاول تاني.',
        generic: 'حصلت مشكلة. من فضلك حاول تاني.',
      },
      success: {
        title: 'تمام! مكانك اتحجز 🎉',
        body: 'حفظنا مكانك. فريقنا هيتواصل معاك خلال يوم واحد عشان يجهّزلك برنامج الولاء بتاعك.',
        note: 'تابع إيميلك — هنكلمك قريب جدًا.',
        back: 'الرجوع للرئيسية',
      },
    },
    privacy: {
      title: 'سياسة الخصوصية',
      updated: 'آخر تحديث: ٢٨ يونيو ٢٠٢٦',
      intro:
        'بتوضّح السياسة دي إيه المعلومات اللي Stampn بتجمعها من خلال الموقع ده وإزاي بنستخدمها. Stampn منصّة ولاء ومكافآت رقمية، والموقع ده حاليًا صفحة «قريبًا» قبل الإطلاق فيها فورم تواصل.',
      collectH: 'إيه اللي بنجمعه',
      collectP: 'لمّا تبعت فورم الدعم، بنجمع المعلومات اللي إنت بتختار تبعتها لنا:',
      collectList: ['اسمك', 'بريدك الإلكتروني', 'الموضوع والرسالة اللي بتكتبها'],
      collectNote:
        'إحنا مش بنجمع المعلومات دي بأي طريقة تانية على الموقع، ومش بنستخدم كوكيز تتبّع أو إعلانات.',
      useH: 'بنستخدمها إزاي',
      useP: 'بنستخدم المعلومات اللي بتبعتها لغرض واحد بس: إننا نقرأ رسالتك ونرد عليك على الإيميل. مش بنبيعها ولا بنأجّرها ولا بنشاركها مع أي طرف تالت لأغراض تسويقية. رسالتك بتوصل لفريقنا عن طريق مزوّد خدمة الفورم بس عشان نستلمها ونرد عليها.',
      keepH: 'بنحتفظ بيها قد إيه',
      keepP: 'بنحتفظ برسالتك للمدة اللي نحتاجها بس عشان نتعامل مع طلبك ونكمّل المراسلات معاك. بعد كده بنمسحها.',
      deleteH: 'طلب الحذف',
      deleteP1: 'تقدر تطلب مننا نمسح المعلومات اللي بعتّها في أي وقت. ابعت إيميل على',
      deleteP2: 'من نفس العنوان اللي استخدمته واطلب حذف بياناتك، وهنشيلها من بريدنا وسجلاتنا.',
      contactH: 'تواصل',
      contactP: 'لأي سؤال عن الخصوصية، تواصل معنا على',
    },
    footer: {
      rights: 'كل الحقوق محفوظة.',
      tagline: 'اتعمل لمستقبل الولاء.',
    },
    notFound: {
      title: '٤٠٤',
      lead: 'ملقيناش الصفحة دي.',
      cta: 'الرجوع للرئيسية',
    },
    seo: {
      home: {
        title: 'Stampn — كروت ولاء رقمية في محفظة عملائك',
        description:
          'Stampn منصّة ولاء ومكافآت رقمية للكافيهات والمطاعم والصالونات والجيمات والمحلات. العملاء بيضيفوا كروت الأختام والنقاط على Apple Wallet و Google Wallet — من غير أي تطبيق. اتعملت لمصر، بالعربي الأول.',
      },
      support: {
        title: 'الدعم — Stampn',
        description: 'عندك سؤال عن Stampn؟ ابعتلنا رسالة وهنرد عليك على الإيميل.',
      },
      getStarted: {
        title: 'ابدأ الآن — Stampn',
        description:
          'سيب بياناتك وفريق Stampn هيتواصل معاك خلال يوم واحد عشان يجهّزلك برنامج الولاء الرقمي بتاعك.',
      },
      privacy: {
        title: 'سياسة الخصوصية — Stampn',
        description: 'إزاي Stampn بتتعامل مع المعلومات اللي بتبعتها من خلال فورم التواصل.',
      },
    },
  },
}

export { CONTACT_EMAIL }

// ── Context ───────────────────────────────────────────────────────────────────
export const LangContext = createContext({ lang: 'en', t: translations.en })

export function useLang() {
  return useContext(LangContext)
}

// Given the current pathname and a target language, return the equivalent path
// in that language (e.g. "/support" + "ar" → "/ar/support").
export function localizePath(pathname, targetLang) {
  // Strip a leading "/ar" to get the language-agnostic sub-path.
  let sub = pathname.replace(/^\/ar(?=\/|$)/, '')
  if (sub === '') sub = '/'
  if (targetLang === 'ar') {
    return sub === '/' ? '/ar' : `/ar${sub}`
  }
  return sub
}
