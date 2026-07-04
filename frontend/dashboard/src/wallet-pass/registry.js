// Template registry — the single source of truth that maps a template id to its
// component, default theme, and a realistic sample payload. The gallery and any
// picker iterate this; nothing hardcodes template lists elsewhere.
import {
  LoyaltyPass,
  EventPass,
  BoardingPass,
  MembershipPass,
  CouponPass,
  GiftCardPass,
  InvitationPass,
  SpecialOccasionPass,
} from './templates'

export const TEMPLATES = [
  {
    id: 'loyalty',
    name: 'Loyalty',
    component: LoyaltyPass,
    theme: { bg: 'linear-gradient(165deg, #E5451C 0%, #C4211C 100%)', fg: '#FFFFFF', accent: '#F2B23C' },
    sample: {
      brand: 'Buns & Bros',
      offer: "4th Time's the Bite -",
      title: 'Free Burger!',
      customerName: '{full_name}',
      memberId: '{c_id}',
      qr: 'stampn:loyalty:BB-2048',
      rewardProgress: 4,
      rewardTarget: 5,
      stampEmoji: '🍔',
      rewardEmoji: '🛍️',
    },
    // Extra gallery examples showing the same loyalty template in other brands
    // (matches the reference Loyalty sheet: burger · donut · coffee). The picker
    // still shows only the primary sample above.
    variants: [
      {
        theme: { bg: 'linear-gradient(165deg, #F98207 0%, #EF6C00 100%)', fg: '#FFFFFF', accent: '#F2A93C' },
        sample: {
          brand: 'Yum Donuts',
          offer: 'Your 5th Visit =',
          title: 'Free Donut!',
          memberId: '{c_id}',
          expiration: '{date}',
          qr: 'stampn:loyalty:YD-5501',
          rewardProgress: 2,
          rewardTarget: 5,
          stampEmoji: '🍩',
          rewardEmoji: '🛍️',
        },
      },
      {
        theme: { bg: 'linear-gradient(165deg, #5A3A22 0%, #3B2716 100%)', fg: '#FFFFFF', accent: '#C9A063' },
        sample: {
          brand: 'Cafe Muse',
          offer: 'Reward on 5th visit',
          title: 'FREE COFFEE',
          customerName: '{full_name}',
          memberId: '{c_id}',
          qr: 'stampn:loyalty:CM-3300',
          rewardProgress: 3,
          rewardTarget: 5,
          stampEmoji: '☕',
          rewardEmoji: '🛍️',
        },
      },
    ],
  },
  {
    id: 'event',
    name: 'Event',
    component: EventPass,
    theme: 'black',
    sample: {
      brand: 'EDM Concert',
      title: 'VIP Concert Access',
      info: [
        { label: 'Valid till', value: '20/08/2024' },
        { label: 'Valid only at', value: 'NYC, USA' },
      ],
      barcodeValue: '739377923334',
      code: '739377923334',
      footerNote: 'Scan at entrance',
      heroPlaceholder: { gradient: 'linear-gradient(135deg, #6B0F0F, #C0341A)', emoji: '🎤' },
    },
    // The rest of the reference Event sheet: wedding · save-the-date · holiday ·
    // fitness · yoga (Spirit Airlines is the separate Boarding template).
    variants: [
      {
        theme: { bg: 'linear-gradient(165deg, #8A2A6A 0%, #6E1B52 100%)', fg: '#FFFFFF', accent: '#E7B6D6' },
        sample: {
          brand: 'Mary ♥ Johns',
          label: 'You are invited',
          title: 'Katherine Max',
          info: [
            { label: 'April 10, 2024', value: '123, 1st Street' },
            { label: '11:30 – 4:30', value: 'Alvisia Way' },
          ],
          barcodeValue: '739377923334',
          code: '739377923334',
          footerNote: 'Scan at entrance',
          heroPlaceholder: { gradient: 'linear-gradient(135deg, #D8C7D6, #EFE6EC)', emoji: '👰' },
        },
      },
      {
        theme: { bg: 'linear-gradient(165deg, #1C7C3D 0%, #14532B 100%)', fg: '#FFFFFF', accent: '#8CE0AC' },
        sample: {
          brand: 'Save the date',
          label: 'Golden Jubilee',
          title: 'Anna & Mark',
          info: [
            { label: 'Ceremony', value: '20/08/2024' },
            { label: 'Venue', value: '123 Beach St, NYC' },
          ],
          barcodeValue: '739377923334',
          code: '739377923334',
          heroPlaceholder: { gradient: 'linear-gradient(135deg, #E9D8C3, #D8BFA3)', emoji: '💍' },
        },
      },
      {
        theme: { bg: 'linear-gradient(165deg, #E4F5EC 0%, #D2EFE0 100%)', fg: '#123A2C', accent: '#1C7C73' },
        sample: {
          brand: 'Holiday Celebrations',
          label: 'You are invited',
          title: 'Amy Jones',
          info: [
            { label: 'Venue', value: 'Coco park' },
            { label: 'July 4th', value: '11:30 PM' },
          ],
          barcodeValue: '739377923334',
          code: '739377923334',
          heroPlaceholder: { gradient: 'linear-gradient(135deg, #FFE08A, #7ED08A)', emoji: '🍍' },
        },
      },
      {
        theme: 'black',
        sample: {
          brand: 'Fitness Pass',
          label: 'Grand Opening',
          title: 'Free 1 hour session',
          info: [
            { label: '123, 1st Street', value: 'Alvisia Way' },
            { label: 'Open from', value: '9:00 AM – 5:00 PM' },
          ],
          barcodeValue: '739377923334',
          code: '739377923334',
          footerNote: 'Scan at entrance',
          heroPlaceholder: { gradient: 'linear-gradient(135deg, #3A3A3F, #6A6A70)', emoji: '🏋️' },
        },
      },
      {
        theme: { bg: 'linear-gradient(165deg, #9E2233 0%, #7A1626 100%)', fg: '#FFFFFF', accent: '#E7A6AE' },
        sample: {
          brand: 'Yoga Studio',
          label: 'Grand Opening',
          title: 'Free 1 hour session',
          info: [
            { label: '123, 1st Street', value: 'Alvisia Way' },
            { label: 'Open from', value: '9:00 AM – 5:00 PM' },
          ],
          barcodeValue: '739377923334',
          code: '739377923334',
          footerNote: 'Scan at entrance',
          heroPlaceholder: { gradient: 'linear-gradient(135deg, #C9A0A8, #E6CCD0)', emoji: '🧘' },
        },
      },
    ],
  },
  {
    id: 'boarding',
    name: 'Boarding',
    component: BoardingPass,
    theme: 'yellow',
    sample: {
      brand: 'Spirit Airlines',
      route: 'SFO – LAX',
      passenger: 'John Doe',
      seat: '25B',
      gate: 'A4',
      flightNo: 'NK 812',
      boardingTime: '10:15 AM',
      date: '10/10/2025',
      qr: 'stampn:boarding:339295373239',
      code: '339295373239',
    },
  },
  {
    id: 'membership',
    name: 'Membership',
    component: MembershipPass,
    theme: 'brown',
    sample: {
      brand: 'Iron & Oak',
      tier: 'Gold',
      memberName: 'Sara Malik',
      memberId: 'IO-100294',
      expiry: '12/2026',
      barcodeValue: '739377923334',
      code: '739377923334',
    },
  },
  {
    id: 'coupon',
    name: 'Coupon',
    component: CouponPass,
    theme: 'orange',
    sample: {
      brand: 'Slice House',
      offer: 'Weekend special',
      discount: '25% OFF',
      expiry: 'Aug 30, 2025',
      validAt: 'In-store & online',
      barcodeValue: '739377923334',
      code: '739377923334',
    },
  },
  {
    id: 'giftcard',
    name: 'Gift Card',
    component: GiftCardPass,
    theme: 'purple',
    sample: {
      brand: 'Café Delights',
      balance: '$50.00',
      cardNumber: '•••• 3239',
      barcodeValue: 'stampn:gift:339295373239',
      code: '3392 9537 3239',
    },
  },
  {
    id: 'invitation',
    name: 'Invitation',
    component: InvitationPass,
    theme: { bg: 'linear-gradient(165deg, #FBE79A 0%, #F5DE7C 100%)', fg: '#3A2E00', accent: '#C6862A' },
    sample: {
      brand: 'You are invited!',
      label: 'Join us to celebrate',
      title: "Ria's Birthday",
      guest: 'Amy Jones',
      time: '7:00 PM',
      date: 'April 10, 2025',
      location: '#7th Ave, Moore St. NYC',
      barcodeValue: '739377923334',
      code: '739377923334',
      heroPlaceholder: { gradient: 'linear-gradient(135deg, #7EC8E3, #A7D96A)', emoji: '🎈' },
    },
  },
  {
    id: 'special',
    name: 'Special Occasion',
    component: SpecialOccasionPass,
    theme: { bg: 'linear-gradient(160deg, #EE1C6A 0%, #D10E5A 100%)', fg: '#FFFFFF', accent: '#FFD25E' },
    sample: {
      brand: 'Café Delights',
      holidayTitle: "Happy Mother's Day",
      offer: '20% OFF',
      validOn: 'May 11, 2025',
      validAt: 'In-store & online',
      qr: 'stampn:promo:739377923334',
      code: '739377923334',
      artworkPlaceholder: { gradient: 'linear-gradient(135deg, #F7D9E6, #E59AB8)', emoji: '💐' },
    },
    // Rest of the reference Special Occasions sheet: Valentine's · Date Night.
    variants: [
      {
        theme: { bg: 'linear-gradient(165deg, #F0453E 0%, #D6241C 100%)', fg: '#FFFFFF', accent: '#FFD25E' },
        sample: {
          brand: 'Café Delights',
          holidayTitle: 'Happy Valentines',
          offer: '$50 OFF',
          validOn: 'Feb 14, 2025',
          validAt: 'In-store & online',
          qr: 'stampn:promo:valentines',
          code: '739377923334',
          artworkPlaceholder: { gradient: 'linear-gradient(135deg, #F04B4B, #C21F1F)', emoji: '❤️' },
        },
      },
      {
        theme: { bg: 'linear-gradient(165deg, #6AA0AA 0%, #4F7F89 100%)', fg: '#FFFFFF', accent: '#CDEAEF' },
        sample: {
          brand: 'Date Night',
          holidayTitle: "It's just",
          offer: 'You & Me',
          info: [
            { label: 'Join me at', value: 'Applebees, NYC' },
            { label: 'Time', value: '7:00 PM' },
          ],
          qr: 'stampn:promo:datenight',
          code: '739377923334',
          artworkPlaceholder: { gradient: 'linear-gradient(135deg, #3A2A4A, #C98A6A)', emoji: '🌇' },
        },
      },
    ],
  },
]

export const TEMPLATE_BY_ID = Object.fromEntries(TEMPLATES.map((tpl) => [tpl.id, tpl]))

// Flattened cards for the showcase gallery: each template's primary sample plus
// any `variants` (e.g. the three loyalty brands). The picker uses TEMPLATES
// directly (one card per type); only the gallery expands variants.
export const GALLERY_CARDS = TEMPLATES.flatMap((tpl) => {
  const base = { key: tpl.id, name: tpl.name, component: tpl.component, theme: tpl.theme, sample: tpl.sample }
  const variants = (tpl.variants || []).map((v, i) => ({
    key: `${tpl.id}-${i + 1}`,
    name: tpl.name,
    component: tpl.component,
    theme: v.theme || tpl.theme,
    sample: v.sample,
  }))
  return [base, ...variants]
})
