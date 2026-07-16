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
  pricing: { en: '/pricing', ar: '/ar/pricing' },
  about: { en: '/about', ar: '/ar/about' },
  contact: { en: '/contact', ar: '/ar/contact' },
  support: { en: '/support', ar: '/ar/support' },
  privacy: { en: '/privacy', ar: '/ar/privacy' },
  refund: { en: '/refund', ar: '/ar/refund' },
  getStarted: { en: '/get-started', ar: '/ar/get-started' },
}

export const translations = {
  en: {
    dir: 'ltr',
    nav: {
      home: 'Home',
      pricing: 'Pricing',
      about: 'About',
      contact: 'Contact',
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
      ctaPrimary: 'Get started',
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
      // Condensed pricing band linking to the full Pricing page.
      pricingBand: {
        title: 'Simple, transparent pricing',
        sub: 'Plans that grow with you — from your first café to a full chain.',
        perMonth: '/mo',
        popular: 'Most popular',
        seeAll: 'See full pricing',
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
    pricing: {
      pill: 'Pricing',
      title: 'Simple, honest',
      titleAccent: 'pricing.',
      lead: 'Every plan gives you real Apple & Google Wallet passes carrying your own logo and colours. Start with a 14-day free trial at Growth level — no card required.',
      monthly: 'Monthly',
      annual: 'Annual',
      annualNote: '2 months free',
      perMonth: '/ mo',
      perYear: '/ yr',
      billedAnnually: 'billed annually',
      currency: 'EGP',
      popular: 'Most popular',
      trialNote: 'All paid plans start with a 14-day free trial. No credit card to begin.',
      cta: 'Get started',
      contactCta: 'Contact sales',
      plans: [
        {
          key: 'starter',
          name: 'Starter',
          tagline: 'One shop, done right.',
          monthly: 599,
          annual: 5990,
          features: [
            '1 loyalty card · up to 2 locations',
            'Up to 5 staff · 2,000 customers',
            'Real Apple & Google Wallet passes',
            'Your logo + brand colours on the pass',
            'Enrollment QR + printable poster',
            'Customer export (CSV)',
            'Basic analytics',
          ],
        },
        {
          key: 'growth',
          name: 'Growth',
          tagline: 'Your brand, everywhere.',
          monthly: 999,
          annual: 9990,
          popular: true,
          features: [
            'Everything in Starter, plus:',
            'Up to 10 cards · 10 locations · 25 staff',
            '20,000 customers',
            'Full pass design — templates, stamp icons & layout, custom images',
            'Branded join page (theme, cover, fonts)',
            'Full analytics + 5 automations',
            'Specialised staff roles + referral program',
          ],
        },
        {
          key: 'chain',
          name: 'Chain',
          tagline: 'For established brands.',
          monthly: 2499,
          annual: 24990,
          features: [
            'Everything in Growth, plus:',
            'Unlimited cards, locations & staff',
            'Unlimited customers',
            'Custom join-page domain',
            'Account manager + SLA',
          ],
        },
        {
          key: 'enterprise',
          name: 'Enterprise',
          tagline: 'Built around how your business works.',
          custom: true,
          priceLabel: "Let's talk",
          features: [
            'Everything in Chain, plus:',
            'Full API + webhooks to your POS / ERP',
            'We build the integration for you',
            'Two-way sync',
            'Single sign-on (SSO)',
            'Priority, dedicated support',
          ],
        },
      ],
    },
    about: {
      pill: 'About Stampn',
      title: 'Loyalty that lives in',
      titleAccent: "your customer's pocket.",
      lead: 'Stampn is a digital loyalty and rewards platform built for Egypt. We turn the paper stamp card every café hands out into a living Apple Wallet and Google Wallet pass — no app to download, for you or your customers.',
      sections: [
        {
          h: 'Why we exist',
          p: 'The paper stamp card is one of the oldest marketing tools there is — and one of the most broken. Customers lose it, forget it, or leave it at home. The business never learns who its regulars are, can never reach them, and never sees the data. We built Stampn to fix exactly that, without asking anyone to install a thing.',
        },
        {
          h: 'What we build',
          p: 'A dashboard a business sets up in minutes, and a wallet pass a customer adds with one tap. Run stamp cards and points programs, design a pass that carries your logo and colours, and push a customer a stamp that updates on their lock screen the instant they earn it. Everything a paper card can’t do.',
        },
        {
          h: 'Built for Egypt, Arabic-first',
          p: 'We’re based in Cairo and built Stampn Arabic-first for cafés, restaurants, salons, gyms, and shops across Egypt and the region. Real Egyptian pound pricing, local payment methods, and a product that reads right in Arabic and English alike.',
        },
        {
          h: 'How we think about it',
          p: 'The real competitor isn’t another loyalty app — it’s a paper card that costs 200 EGP once. So we sell what paper never can: you learn who your customers are, you can reach them, you can see the data, and they can’t lose the card. We grow with a business as it grows, and we never punish anyone for succeeding.',
        },
      ],
      ctaTitle: 'Ready to see it?',
      ctaBody: 'Start a 14-day free trial, or talk to us about your business.',
      ctaPrimary: 'Get started',
      ctaSecondary: 'Contact us',
    },
    contact: {
      pill: 'Contact',
      title: 'Talk to',
      titleAccent: 'a human.',
      lead: 'Questions about pricing, setup, or your account? Reach us any of these ways — real people, based in Cairo.',
      emailH: 'Email',
      emailSub: 'We reply within one business day.',
      phoneH: 'Phone / WhatsApp',
      phoneSub: 'Sun–Thu, 10:00–18:00 (Cairo time).',
      addressH: 'Address',
      addressSub: 'Stampn — Cairo, Egypt.',
      formH: 'Prefer to write?',
      formP: 'Send us a detailed message and we’ll reply by email.',
      formCta: 'Go to the contact form',
    },
    refund: {
      title: 'Refund & Cancellation Policy',
      updated: 'Last updated: 15 July 2026',
      intro:
        'This policy explains how billing, cancellation, and refunds work for a Stampn subscription. By subscribing to a paid plan you agree to the terms below.',
      noRefundH: 'No refunds',
      noRefundP:
        'All subscription payments are non-refundable. We do not offer refunds or credits for partially used billing periods, unused features, or for the time remaining after you cancel. Before you pay, you can try Stampn free for 14 days so you know exactly what you’re getting.',
      cancelH: 'Cancelling your subscription',
      cancelP:
        'You can cancel your subscription at any time from your dashboard, or by contacting us. Cancelling stops the next renewal — you will not be charged again.',
      afterH: 'What happens after you cancel',
      afterP:
        'When you cancel, your subscription stays active until the end of the current paid period. You keep full access to everything on your plan through that date; at the end of the period the subscription simply ends and is not renewed. We do not prorate or refund the remainder of the period.',
      trialH: 'Free trial',
      trialP:
        'Paid plans begin with a 14-day free trial. You are not charged during the trial. If you cancel before the trial ends, you are never billed. If you don’t cancel, your subscription starts and the plan’s price is charged for the first period.',
      howH: 'How to cancel',
      howP: 'Cancel from the billing section of your dashboard, or email us and we’ll take care of it:',
      contactH: 'Questions',
      contactP: 'For any billing question, contact us at',
    },
    footer: {
      rights: 'All rights reserved.',
      tagline: 'Built for the future of loyalty.',
      productH: 'Product',
      companyH: 'Company',
      legalH: 'Legal',
      pricing: 'Pricing',
      about: 'About us',
      contact: 'Contact us',
      support: 'Support',
      privacy: 'Privacy Policy',
      refund: 'Refund & Cancellation',
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
      pricing: {
        title: 'Pricing — Stampn',
        description:
          'Simple, honest pricing for Stampn: Starter, Growth, Chain and Custom plans in EGP. Every plan gives real Apple & Google Wallet passes with your brand. 14-day free trial.',
      },
      about: {
        title: 'About us — Stampn',
        description:
          'Stampn is a digital loyalty and rewards platform built in Cairo, Egypt — turning the paper stamp card into a living Apple Wallet and Google Wallet pass. No app needed.',
      },
      contact: {
        title: 'Contact us — Stampn',
        description:
          'Get in touch with Stampn: email contact@stampn.net, phone +20 101 542 5157, Cairo, Egypt.',
      },
      refund: {
        title: 'Refund & Cancellation Policy — Stampn',
        description:
          'How billing, cancellation, and refunds work for a Stampn subscription. Cancel anytime; access continues until the end of your paid period.',
      },
    },
  },

  ar: {
    dir: 'rtl',
    nav: {
      home: 'الرئيسية',
      pricing: 'الأسعار',
      about: 'من نحن',
      contact: 'تواصل معنا',
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
      // شريط أسعار مختصر بيوصل لصفحة الأسعار الكاملة.
      pricingBand: {
        title: 'أسعار بسيطة وواضحة',
        sub: 'باقات بتكبر معاك — من أول كافيه لحد سلسلة كاملة.',
        perMonth: '/شهر',
        popular: 'الأكثر شيوعًا',
        seeAll: 'شوف كل الأسعار',
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
    pricing: {
      pill: 'الأسعار',
      title: 'أسعار بسيطة',
      titleAccent: 'وواضحة.',
      lead: 'كل باقة بتديك باسات حقيقية على Apple Wallet و Google Wallet بشعارك وألوانك. ابدأ بتجربة مجانية ١٤ يوم على مستوى Growth — من غير كارت ائتمان.',
      monthly: 'شهري',
      annual: 'سنوي',
      annualNote: 'شهرين مجانًا',
      perMonth: '/ شهر',
      perYear: '/ سنة',
      billedAnnually: 'بتتحاسب سنويًا',
      currency: 'ج.م',
      popular: 'الأكثر شيوعًا',
      trialNote: 'كل الباقات المدفوعة بتبدأ بتجربة مجانية ١٤ يوم. من غير كارت ائتمان في الأول.',
      cta: 'ابدأ الآن',
      contactCta: 'كلّم المبيعات',
      plans: [
        {
          key: 'starter',
          name: 'Starter',
          tagline: 'محل واحد، بشكل صح.',
          monthly: 599,
          annual: 5990,
          features: [
            'كارت ولاء واحد · لحد فرعين',
            'لحد ٥ موظفين · ٢٬٠٠٠ عميل',
            'باسات حقيقية على Apple و Google Wallet',
            'شعارك وألوان علامتك على الباس',
            'كود QR للتسجيل + بوستر للطباعة',
            'تصدير العملاء (CSV)',
            'تحليلات أساسية',
          ],
        },
        {
          key: 'growth',
          name: 'Growth',
          tagline: 'علامتك في كل مكان.',
          monthly: 999,
          annual: 9990,
          popular: true,
          features: [
            'كل مميزات Starter، وكمان:',
            'لحد ١٠ كروت · ١٠ فروع · ٢٥ موظف',
            '٢٠٬٠٠٠ عميل',
            'تصميم كامل للباس — قوالب، أيقونات وترتيب الأختام، صور مخصّصة',
            'صفحة انضمام بعلامتك (ثيم، غلاف، خطوط)',
            'تحليلات كاملة + ٥ أتمتة',
            'أدوار موظفين متخصّصة + برنامج إحالة',
          ],
        },
        {
          key: 'chain',
          name: 'Chain',
          tagline: 'للعلامات الكبيرة.',
          monthly: 2499,
          annual: 24990,
          features: [
            'كل مميزات Growth، وكمان:',
            'كروت وفروع وموظفين بلا حدود',
            'عملاء بلا حدود',
            'دومين مخصّص لصفحة الانضمام',
            'مدير حساب + اتفاقية مستوى خدمة',
          ],
        },
        {
          key: 'enterprise',
          name: 'Enterprise',
          tagline: 'مبني على طريقة شغل شركتك.',
          custom: true,
          priceLabel: 'خلينا نتكلم',
          features: [
            'كل مميزات Chain، وكمان:',
            'API كامل + Webhooks لنظام الكاشير / ERP',
            'إحنا بنعملّك التكامل',
            'مزامنة في الاتجاهين',
            'تسجيل دخول موحّد (SSO)',
            'دعم مخصّص بأولوية',
          ],
        },
      ],
    },
    about: {
      pill: 'من نحن',
      title: 'ولاء بيعيش',
      titleAccent: 'في جيب عميلك.',
      lead: 'Stampn منصّة ولاء ومكافآت رقمية اتعملت لمصر. بنحوّل كارت الأختام الورقي اللي كل كافيه بيوزّعه لباس حيّ على Apple Wallet و Google Wallet — من غير أي تطبيق، لا ليك ولا لعملائك.',
      sections: [
        {
          h: 'ليه بنعمل ده',
          p: 'كارت الأختام الورقي من أقدم أدوات التسويق — ومن أكترها عطلًا. العميل بيضيّعه أو بينساه أو بيسيبه في البيت. والنشاط عمره ما بيعرف مين عملاؤه الدائمين، ولا بيقدر يوصلهم، ولا بيشوف أي بيانات. عملنا Stampn عشان نحل ده بالظبط، من غير ما نطلب من حد يثبّت أي حاجة.',
        },
        {
          h: 'إيه اللي بنبنيه',
          p: 'لوحة تحكم بتتظبط في دقايق، وباس بيضيفه العميل بضغطة واحدة. اعمل كروت أختام وبرامج نقاط، صمّم باس بشعارك وألوانك، وابعت للعميل ختم بيتحدّث على شاشة القفل في نفس اللحظة اللي بياخده فيها. كل اللي الكارت الورقي مش قادر يعمله.',
        },
        {
          h: 'اتعمل لمصر، بالعربي الأول',
          p: 'إحنا في القاهرة، وبنينا Stampn بالعربي الأول للكافيهات والمطاعم والصالونات والجيمات والمحلات في مصر والمنطقة. أسعار بالجنيه المصري، وسائل دفع محلية، ومنتج بيتقري صح بالعربي والإنجليزي.',
        },
        {
          h: 'إزاي بنفكّر',
          p: 'المنافس الحقيقي مش تطبيق ولاء تاني — ده كارت ورقي بيتكلّف ٢٠٠ جنيه مرة واحدة. فإحنا بنبيع اللي الورق مش قادر يعمله: تعرف مين عملاؤك، تقدر توصلهم، تشوف البيانات، وهما مش هيضيّعوا الكارت. بنكبر مع النشاط وهو بيكبر، وعمرنا ما بنعاقب حد على نجاحه.',
        },
      ],
      ctaTitle: 'جاهز تشوفه؟',
      ctaBody: 'ابدأ تجربة مجانية ١٤ يوم، أو كلّمنا عن نشاطك.',
      ctaPrimary: 'ابدأ الآن',
      ctaSecondary: 'تواصل معنا',
    },
    contact: {
      pill: 'تواصل معنا',
      title: 'اتكلم مع',
      titleAccent: 'ناس حقيقية.',
      lead: 'عندك سؤال عن الأسعار أو التفعيل أو حسابك؟ اوصلنا بأي طريقة من دول — ناس حقيقية في القاهرة.',
      emailH: 'البريد الإلكتروني',
      emailSub: 'بنرد خلال يوم عمل واحد.',
      phoneH: 'تليفون / واتساب',
      phoneSub: 'الأحد–الخميس، ١٠ ص – ٦ م (توقيت القاهرة).',
      addressH: 'العنوان',
      addressSub: 'Stampn — القاهرة، مصر.',
      formH: 'تفضّل تكتب؟',
      formP: 'ابعتلنا رسالة مفصّلة وهنرد عليك على الإيميل.',
      formCta: 'روح لفورم التواصل',
    },
    refund: {
      title: 'سياسة الاسترداد والإلغاء',
      updated: 'آخر تحديث: ١٥ يوليو ٢٠٢٦',
      intro:
        'بتوضّح السياسة دي إزاي بيشتغل الدفع والإلغاء والاسترداد لاشتراك Stampn. باشتراكك في أي باقة مدفوعة إنت موافق على الشروط اللي تحت.',
      noRefundH: 'مفيش استرداد',
      noRefundP:
        'كل مدفوعات الاشتراك غير قابلة للاسترداد. مش بنقدّم استرداد ولا رصيد عن فترات اتستخدمت جزئيًا، ولا مميزات ماتستخدمتش، ولا عن المدة المتبقية بعد الإلغاء. قبل ما تدفع، تقدر تجرّب Stampn مجانًا ١٤ يوم عشان تعرف بالظبط بتاخد إيه.',
      cancelH: 'إلغاء الاشتراك',
      cancelP:
        'تقدر تلغي اشتراكك في أي وقت من لوحة التحكم، أو بالتواصل معانا. الإلغاء بيوقف التجديد الجاي — مش هيتم خصم تاني منك.',
      afterH: 'بيحصل إيه بعد الإلغاء',
      afterP:
        'لمّا تلغي، اشتراكك بيفضل شغّال لحد نهاية الفترة المدفوعة الحالية. بتفضل واصل لكل مميزات باقتك لحد التاريخ ده؛ وفي نهاية الفترة الاشتراك بيخلص وبس ومش بيتجدّد. مش بنحسب أو نرجّع أي مبلغ عن باقي الفترة.',
      trialH: 'التجربة المجانية',
      trialP:
        'الباقات المدفوعة بتبدأ بتجربة مجانية ١٤ يوم. مفيش خصم خلال التجربة. لو ألغيت قبل ما التجربة تخلص، مش هيتم محاسبتك خالص. لو ماألغتش، الاشتراك بيبدأ ويتخصم سعر الباقة عن أول فترة.',
      howH: 'إزاي تلغي',
      howP: 'الغِ من قسم الفواتير في لوحة التحكم، أو ابعتلنا إيميل وإحنا هنتصرّف:',
      contactH: 'أسئلة',
      contactP: 'لأي سؤال عن الفواتير، تواصل معنا على',
    },
    footer: {
      rights: 'كل الحقوق محفوظة.',
      tagline: 'اتعمل لمستقبل الولاء.',
      productH: 'المنتج',
      companyH: 'الشركة',
      legalH: 'قانوني',
      pricing: 'الأسعار',
      about: 'من نحن',
      contact: 'تواصل معنا',
      support: 'الدعم',
      privacy: 'سياسة الخصوصية',
      refund: 'الاسترداد والإلغاء',
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
      pricing: {
        title: 'الأسعار — Stampn',
        description:
          'أسعار بسيطة وواضحة لـ Stampn: باقات Starter و Growth و Chain و Custom بالجنيه المصري. كل باقة بتديك باسات حقيقية على Apple و Google Wallet بعلامتك. تجربة مجانية ١٤ يوم.',
      },
      about: {
        title: 'من نحن — Stampn',
        description:
          'Stampn منصّة ولاء ومكافآت رقمية اتعملت في القاهرة، مصر — بتحوّل كارت الأختام الورقي لباس حيّ على Apple Wallet و Google Wallet. من غير أي تطبيق.',
      },
      contact: {
        title: 'تواصل معنا — Stampn',
        description:
          'اوصل لـ Stampn: إيميل contact@stampn.net، تليفون ‎+20 101 542 5157، القاهرة، مصر.',
      },
      refund: {
        title: 'سياسة الاسترداد والإلغاء — Stampn',
        description:
          'إزاي بيشتغل الدفع والإلغاء والاسترداد لاشتراك Stampn. الغِ في أي وقت؛ الوصول بيفضل لحد نهاية فترتك المدفوعة.',
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
