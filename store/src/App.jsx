import { useState } from 'react'

const products = [
  {
    id: 1,
    name: 'Daily Multivitamin',
    sku: 'DM-01',
    price: '$42',
    desc: 'Complete daily nutrition with 23 essential vitamins & minerals — the same you\'d buy for yourself.',
    bgCard: 'bg-amber-50',
    bgPill: 'bg-amber-200',
    tag: 'Best Seller',
  },
  {
    id: 2,
    name: 'Hip & Joint',
    sku: 'HJ-02',
    price: '$48',
    desc: 'Glucosamine, chondroitin & MSM for lasting mobility and comfort in every stride.',
    bgCard: 'bg-emerald-50',
    bgPill: 'bg-emerald-200',
    tag: 'Vet Favorite',
  },
  {
    id: 3,
    name: 'Calm & Focused',
    sku: 'CF-03',
    price: '$44',
    desc: 'L-theanine & ashwagandha for a clear, relaxed mind — without the sedation.',
    bgCard: 'bg-sky-50',
    bgPill: 'bg-sky-200',
    tag: 'New',
  },
  {
    id: 4,
    name: 'Skin & Coat',
    sku: 'SC-04',
    price: '$40',
    desc: 'Wild-caught omega-3 fish oil & biotin for a shiny, itch-free coat year-round.',
    bgCard: 'bg-rose-50',
    bgPill: 'bg-rose-200',
    tag: null,
  },
]

const reasons = [
  {
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" d="M14 3v4M14 21v4M3 14h4M21 14h4" />
        <circle cx="14" cy="14" r="6" />
        <circle cx="14" cy="14" r="2" fill="currentColor" stroke="none" />
      </svg>
    ),
    title: 'Human-Grade Ingredients',
    text: 'Every vitamin, probiotic, and fat source meets the same regulatory standard as human supplements — not the looser "feed-grade" rules most pet brands use.',
  },
  {
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" d="M14 4l2.5 7.5H24l-6.5 4.5 2.5 7.5L14 19l-6 4.5 2.5-7.5L4 11.5h7.5z" />
      </svg>
    ),
    title: 'Vet-Formulated',
    text: 'Every formula is developed with veterinary nutritionists and third-party tested for purity, potency, and safety — at every batch, not just launch.',
  },
  {
    icon: (
      <svg className="w-7 h-7" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 14l5.5 5.5L23 8" />
      </svg>
    ),
    title: 'No Fillers. Ever.',
    text: 'No artificial colors, no cheap binders, no mystery ingredients. Just what works — in the exact amounts that make a measurable difference.',
  },
]

const testimonials = [
  {
    quote: "My dog's energy completely transformed after three weeks. I actually started reading the label because the ingredients look like something I'd take myself.",
    author: 'Sarah M.',
    pet: 'Golden Retriever, 4 yrs',
    rating: 5,
  },
  {
    quote: "Finally a supplement without a paragraph of unpronounceable fillers. Max went from barely walking upstairs to running laps at the dog park.",
    author: 'James R.',
    pet: 'Labrador, 8 yrs',
    rating: 5,
  },
  {
    quote: "The vet asked what I changed in Luna's diet. I said I started treating her supplements the same way I treat mine — human-grade only.",
    author: 'Priya K.',
    pet: 'Dachshund, 6 yrs',
    rating: 5,
  },
]

const trustItems = [
  'Free Shipping Over $50',
  '30-Day Guarantee',
  'Vet Formulated',
  'Human-Grade Ingredients',
  'USA Made',
]

function StarRow({ count = 5 }) {
  return (
    <div className="flex gap-0.5 text-sage">
      {Array.from({ length: count }).map((_, i) => (
        <svg key={i} className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="currentColor">
          <path d="M7 1l1.6 4.9H14l-4.1 3 1.6 4.9L7 11l-4.5 2.8 1.6-4.9L0 5.9h5.4z" />
        </svg>
      ))}
    </div>
  )
}

function ProductCard({ product, onAdd }) {
  return (
    <div className="group bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-lg transition-all duration-300 flex flex-col">
      <div className={`${product.bgCard} h-52 flex items-center justify-center relative flex-shrink-0`}>
        {product.tag && (
          <span className="absolute top-4 left-4 bg-sage text-white text-[10px] uppercase tracking-widest px-3 py-1 rounded-full font-semibold">
            {product.tag}
          </span>
        )}
        <div className={`${product.bgPill} w-28 h-36 rounded-2xl shadow flex flex-col items-center justify-center gap-2 group-hover:scale-105 transition-transform duration-300`}>
          <span className="text-3xl select-none">🐾</span>
          <span className="text-[11px] font-semibold text-center leading-tight px-2">{product.name}</span>
          <span className="text-[9px] text-bark/50 font-medium">{product.sku}</span>
        </div>
      </div>
      <div className="p-5 flex flex-col flex-1">
        <h3 className="font-serif text-lg mb-1">{product.name}</h3>
        <p className="text-sm text-bark/60 leading-relaxed flex-1">{product.desc}</p>
        <div className="flex items-center justify-between mt-4">
          <span className="font-semibold text-bark">{product.price}</span>
          <button
            onClick={onAdd}
            className="bg-bark text-cream text-xs px-5 py-2 rounded-full hover:bg-sage transition-colors font-medium tracking-wide"
          >
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [cartCount, setCartCount] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [subscribed, setSubscribed] = useState(false)

  function handleSubscribe(e) {
    e.preventDefault()
    if (email.trim()) setSubscribed(true)
  }

  return (
    <div className="bg-cream min-h-screen font-sans text-bark antialiased">

      {/* ── Announcement bar ── */}
      <div className="bg-sage text-white text-center text-xs py-2.5 tracking-wide font-medium">
        Free shipping on orders over $50 · Subscribe and save 15%
      </div>

      {/* ── Navigation ── */}
      <nav className="sticky top-0 z-50 bg-cream/95 backdrop-blur-sm border-b border-bark/10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-8">

          {/* Logo */}
          <a href="#" className="font-serif text-xl font-normal tracking-tight flex-shrink-0">
            dog is human
          </a>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8 text-sm font-medium">
            <a href="#products" className="hover:text-sage transition-colors">Products</a>
            <a href="#science"  className="hover:text-sage transition-colors">The Science</a>
            <a href="#story"    className="hover:text-sage transition-colors">Our Story</a>
            <a href="#reviews"  className="hover:text-sage transition-colors">Reviews</a>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="md:hidden p-1 rounded-lg hover:bg-bark/5"
              aria-label="Toggle menu"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d={menuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'} />
              </svg>
            </button>

            <button className="relative p-1 rounded-lg hover:bg-bark/5 transition-colors" aria-label="Cart">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
              </svg>
              {cartCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-sage text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                  {cartCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden bg-cream border-t border-bark/10 px-6 py-4 flex flex-col gap-4 text-sm font-medium">
            {['Products', 'The Science', 'Our Story', 'Reviews'].map(label => (
              <a
                key={label}
                href={`#${label.toLowerCase().replace(/\s+/g, '')}`}
                onClick={() => setMenuOpen(false)}
                className="py-1 hover:text-sage transition-colors"
              >
                {label}
              </a>
            ))}
          </div>
        )}
      </nav>

      {/* ── Hero ── */}
      <section className="max-w-6xl mx-auto px-6 py-24 md:py-32 grid md:grid-cols-2 gap-16 items-center">

        {/* Copy */}
        <div className="space-y-7">
          <span className="inline-block text-[11px] uppercase tracking-[0.22em] text-sage font-semibold">
            Human-Grade · Vet-Formulated · USA Made
          </span>

          <h1 className="font-serif text-5xl md:text-[3.6rem] leading-[1.1] font-normal">
            Supplements<br />
            <em>built for dogs,</em><br />
            <strong className="font-semibold">made for humans.</strong>
          </h1>

          <p className="text-bark/65 text-lg leading-relaxed max-w-md">
            Every ingredient in our soft chews is the exact same grade you'd find in a human supplement.
            Because your dog is basically a person.
          </p>

          <div className="flex flex-wrap gap-3 pt-1">
            <a href="#products"
              className="bg-sage text-white px-8 py-3.5 rounded-full text-sm font-semibold tracking-wide hover:opacity-90 transition-opacity">
              Shop Now
            </a>
            <a href="#science"
              className="border border-bark/30 px-8 py-3.5 rounded-full text-sm font-medium tracking-wide hover:border-bark transition-colors">
              The Science
            </a>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-7 pt-2">
            {[['23+', 'Nutrients'], ['30', 'Day Guarantee'], ['100%', 'Human-Grade']].map(([val, label]) => (
              <div key={label} className="text-center">
                <div className="font-serif text-2xl font-semibold leading-none">{val}</div>
                <div className="text-[11px] text-bark/50 mt-1 tracking-wide">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Visual */}
        <div className="relative flex items-center justify-center min-h-[22rem]">
          {/* Outer glow ring */}
          <div className="w-80 h-80 md:w-[22rem] md:h-[22rem] rounded-full bg-tan/25 flex items-center justify-center">
            <div className="w-60 h-60 md:w-64 md:h-64 rounded-full bg-tan/35 flex items-center justify-center">
              {/* Product mock */}
              <div className="w-40 h-52 bg-white rounded-3xl shadow-2xl flex flex-col items-center justify-between py-6 px-5">
                <div className="w-full">
                  <div className="text-[9px] uppercase tracking-widest text-bark/40 font-semibold text-center">Dog is Human</div>
                </div>
                <div className="w-14 h-14 rounded-full bg-sage/15 flex items-center justify-center text-3xl">🐾</div>
                <div className="text-center space-y-1">
                  <div className="font-serif text-sm font-semibold">Daily Multi</div>
                  <div className="text-[10px] text-bark/50">DM-01 · 30 chews</div>
                </div>
                <div className="w-full space-y-1">
                  <div className="flex justify-between text-[9px] text-bark/40">
                    <span>Potency</span><span>100%</span>
                  </div>
                  <div className="h-1 bg-bark/10 rounded-full overflow-hidden">
                    <div className="h-full w-full bg-sage rounded-full" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Floating chips */}
          <div className="absolute top-6 right-4 bg-white rounded-2xl shadow-lg px-4 py-2.5 text-xs font-medium space-y-0.5">
            <div className="text-sage font-semibold flex items-center gap-1.5">
              <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                <path d="M10.5 2.5l-6 6L1.5 5.5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round"/>
              </svg>
              Human-Grade
            </div>
          </div>
          <div className="absolute bottom-10 left-0 bg-white rounded-2xl shadow-lg px-4 py-2.5 text-xs">
            <StarRow />
            <span className="text-bark/50 text-[10px] mt-0.5 block">4.9 · 1,200+ reviews</span>
          </div>
          <div className="absolute top-1/2 -translate-y-1/2 right-0 bg-sage text-white rounded-2xl shadow-lg px-3 py-2 text-[10px] font-medium leading-relaxed">
            Vet<br/>Formulated
          </div>
        </div>
      </section>

      {/* ── Trust bar ── */}
      <div className="border-y border-bark/10 bg-white/60">
        <div className="max-w-6xl mx-auto px-6 py-3.5 flex flex-wrap justify-center gap-x-8 gap-y-2">
          {trustItems.map(item => (
            <span key={item} className="flex items-center gap-2 text-[11px] uppercase tracking-[0.15em] text-bark/50 font-medium">
              <span className="text-sage text-xs">✦</span>
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* ── Products ── */}
      <section id="products" className="max-w-6xl mx-auto px-6 py-24">
        <div className="text-center mb-14">
          <span className="text-[11px] uppercase tracking-[0.22em] text-sage font-semibold">The Collection</span>
          <h2 className="font-serif text-4xl mt-3 font-normal">Built for every dog.</h2>
          <p className="text-bark/55 mt-3 max-w-sm mx-auto leading-relaxed text-sm">
            From puppies to seniors, a targeted formula for every stage and every need.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {products.map(p => (
            <ProductCard key={p.id} product={p} onAdd={() => setCartCount(c => c + 1)} />
          ))}
        </div>
      </section>

      {/* ── Why Human-Grade (dark section) ── */}
      <section id="science" className="bg-bark text-cream">
        <div className="max-w-6xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <span className="text-[11px] uppercase tracking-[0.22em] text-tan font-semibold">Why It Matters</span>
            <h2 className="font-serif text-4xl mt-3 font-normal">The human-grade difference.</h2>
            <p className="text-cream/50 mt-3 max-w-md mx-auto leading-relaxed text-sm">
              Most pet supplements use "feed-grade" ingredients — a category with far looser regulations
              than human-grade. We use human-grade. Full stop.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-12">
            {reasons.map(r => (
              <div key={r.title} className="space-y-5">
                <div className="w-12 h-12 rounded-2xl bg-cream/10 flex items-center justify-center text-tan">
                  {r.icon}
                </div>
                <h3 className="font-serif text-xl font-normal">{r.title}</h3>
                <p className="text-cream/55 leading-relaxed text-sm">{r.text}</p>
              </div>
            ))}
          </div>

          {/* Divider quote */}
          <div className="mt-20 border-t border-cream/10 pt-16 text-center max-w-2xl mx-auto">
            <p className="font-serif text-2xl md:text-3xl text-cream/80 italic leading-relaxed">
              "If you wouldn't take it yourself, why would you give it to your dog?"
            </p>
            <p className="text-cream/35 text-sm mt-4 tracking-wide">— Dog is Human, founding principle</p>
          </div>
        </div>
      </section>

      {/* ── Our Story ── */}
      <section id="story" className="max-w-6xl mx-auto px-6 py-24 grid md:grid-cols-2 gap-16 items-center">
        {/* Image mock */}
        <div className="relative h-80 md:h-[26rem] order-2 md:order-1">
          <div className="absolute inset-0 bg-tan/20 rounded-3xl" />
          <div className="absolute top-6 left-6 right-6 bottom-6 bg-tan/30 rounded-2xl overflow-hidden flex items-center justify-center">
            <div className="text-center space-y-3 p-8">
              <div className="text-7xl select-none">🐕</div>
              <p className="font-serif text-bark/60 text-lg italic leading-relaxed">
                "For the dogs who run the house."
              </p>
            </div>
          </div>
          {/* Corner badge */}
          <div className="absolute -bottom-4 -right-4 bg-sage text-white rounded-2xl shadow-xl p-5 text-center">
            <div className="font-serif text-2xl font-semibold">30</div>
            <div className="text-[10px] uppercase tracking-widest mt-0.5 opacity-80">Day Guarantee</div>
          </div>
        </div>

        {/* Copy */}
        <div className="space-y-6 order-1 md:order-2">
          <span className="text-[11px] uppercase tracking-[0.22em] text-sage font-semibold">Our Story</span>
          <h2 className="font-serif text-4xl font-normal leading-snug">
            Started by dog people,<br />for dog people.
          </h2>
          <p className="text-bark/65 leading-relaxed">
            We noticed something odd: we read every label on our own supplements, scrutinizing source and dosage.
            But we'd been blindly buying pet chews for years — never questioning the ingredients.
          </p>
          <p className="text-bark/65 leading-relaxed">
            That felt wrong. So we started Dog is Human with a single question:
            <em> what would we feed our dogs if we held them to the same standard as ourselves?</em>
            The answer became our entire product line.
          </p>
          <a href="#products"
            className="inline-flex items-center gap-2 border border-bark/30 px-7 py-3 rounded-full text-sm font-medium hover:bg-bark hover:text-cream transition-all group">
            Meet the Products
            <svg className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 14 14">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2 7h10M8 3l4 4-4 4" />
            </svg>
          </a>
        </div>
      </section>

      {/* ── Quality badges ── */}
      <div className="bg-cream border-y border-bark/10">
        <div className="max-w-6xl mx-auto px-6 py-14 grid sm:grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { icon: '🏅', label: 'Human-Grade', sub: 'USP-verified ingredients' },
            { icon: '🔬', label: 'Third-Party Tested', sub: 'Every batch, every time' },
            { icon: '🇺🇸', label: 'Made in USA', sub: 'cGMP certified facility' },
            { icon: '↩️', label: '30-Day Returns', sub: 'No questions asked' },
          ].map(b => (
            <div key={b.label} className="space-y-2">
              <div className="text-3xl">{b.icon}</div>
              <div className="font-semibold text-sm">{b.label}</div>
              <div className="text-bark/45 text-xs">{b.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Testimonials ── */}
      <section id="reviews" className="bg-white">
        <div className="max-w-6xl mx-auto px-6 py-24">
          <div className="text-center mb-14">
            <span className="text-[11px] uppercase tracking-[0.22em] text-sage font-semibold">Reviews</span>
            <h2 className="font-serif text-4xl mt-3 font-normal">
              Dogs don't lie.<br className="hidden sm:block" /> Neither do their parents.
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((t, i) => (
              <div key={i} className="bg-cream rounded-3xl p-7 space-y-5 flex flex-col">
                <StarRow count={t.rating} />
                <p className="text-bark/75 leading-relaxed text-sm italic flex-1">"{t.quote}"</p>
                <div className="border-t border-bark/10 pt-4">
                  <div className="font-semibold text-sm">{t.author}</div>
                  <div className="text-bark/45 text-xs mt-0.5">{t.pet}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Average rating */}
          <div className="mt-12 text-center space-y-2">
            <div className="flex items-center justify-center gap-1">
              <StarRow count={5} />
            </div>
            <div className="text-bark/50 text-sm">4.9 average · 1,200+ verified reviews</div>
          </div>
        </div>
      </section>

      {/* ── Newsletter ── */}
      <section className="bg-sage text-white">
        <div className="max-w-2xl mx-auto px-6 py-24 text-center space-y-7">
          <span className="text-[11px] uppercase tracking-[0.22em] text-white/50 font-semibold">Join the Pack</span>
          <h2 className="font-serif text-4xl font-normal">Good things for good dogs.</h2>
          <p className="text-white/65 leading-relaxed max-w-md mx-auto">
            Subscribe for 15% off your first order, plus science-backed tips on dog nutrition,
            health, and living your best life together.
          </p>

          {subscribed ? (
            <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur rounded-full px-8 py-4 text-sm font-medium">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 16 16">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l3.5 3.5L13 4" />
              </svg>
              You're in! Check your inbox for your discount.
            </div>
          ) : (
            <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                className="flex-1 bg-white text-bark placeholder-bark/40 px-5 py-3.5 rounded-full text-sm outline-none focus:ring-2 ring-white/50"
              />
              <button
                type="submit"
                className="bg-bark text-cream px-8 py-3.5 rounded-full text-sm font-semibold hover:opacity-90 transition-opacity whitespace-nowrap"
              >
                Get 15% Off
              </button>
            </form>
          )}

          <p className="text-white/35 text-xs">No spam. Unsubscribe anytime.</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-bark text-cream">
        <div className="max-w-6xl mx-auto px-6 pt-16 pb-10">
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-10 mb-14">

            {/* Brand */}
            <div className="space-y-5">
              <div className="font-serif text-2xl">dog is human</div>
              <p className="text-cream/45 text-sm leading-relaxed">
                Human-grade supplements for your best friend. Because they deserve nothing less.
              </p>
              <div className="flex gap-2">
                {['IG', 'TK', 'FB'].map(s => (
                  <button key={s}
                    className="w-8 h-8 rounded-full border border-cream/20 flex items-center justify-center text-xs text-cream/45 hover:border-cream/50 hover:text-cream/70 transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Link columns */}
            {[
              { title: 'Shop',    links: ['Daily Multivitamin', 'Hip & Joint', 'Calm & Focused', 'Skin & Coat'] },
              { title: 'Company', links: ['Our Story', 'The Science', 'Sustainability', 'Press'] },
              { title: 'Support', links: ['FAQ', 'Shipping & Returns', '30-Day Guarantee', 'Contact Us'] },
            ].map(col => (
              <div key={col.title} className="space-y-4">
                <div className="text-xs font-semibold tracking-[0.15em] uppercase text-cream/70">{col.title}</div>
                <ul className="space-y-2.5">
                  {col.links.map(l => (
                    <li key={l}>
                      <a href="#" className="text-cream/40 text-sm hover:text-cream/70 transition-colors">{l}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="border-t border-cream/10 pt-8 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-cream/30">
            <span>© {new Date().getFullYear()} Dog is Human. All rights reserved.</span>
            <div className="flex gap-5">
              <a href="#" className="hover:text-cream/55 transition-colors">Privacy Policy</a>
              <a href="#" className="hover:text-cream/55 transition-colors">Terms of Service</a>
              <a href="#" className="hover:text-cream/55 transition-colors">Accessibility</a>
            </div>
          </div>
        </div>
      </footer>

    </div>
  )
}
