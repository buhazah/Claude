/* ============================================================
   Brand JS — Minimal, purposeful
   ============================================================ */

(function () {
  'use strict';

  /* --- Fade-in on scroll --- */
  function initFadeIn() {
    const els = document.querySelectorAll('.fade-in');
    if (!els.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );

    els.forEach((el) => observer.observe(el));
  }

  /* --- Product tabs --- */
  function initProductTabs() {
    const tabs = document.querySelectorAll('.product-tabs__tab');
    if (!tabs.length) return;

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        const container = tab.closest('.product-tabs');

        container.querySelectorAll('.product-tabs__tab').forEach((t) => {
          t.classList.toggle('product-tabs__tab--active', t === tab);
        });

        container.querySelectorAll('.product-tabs__panel').forEach((panel) => {
          panel.classList.toggle(
            'product-tabs__panel--active',
            panel.dataset.panel === target
          );
        });
      });
    });
  }

  /* --- Cart drawer --- */
  function initCartDrawer() {
    const openTriggers = document.querySelectorAll('[data-cart-open]');
    const drawer = document.getElementById('cart-drawer');
    const overlay = document.getElementById('cart-overlay');
    const closeBtn = document.getElementById('cart-close');

    if (!drawer) return;

    function open() {
      drawer.classList.add('cart-drawer--open');
      overlay.classList.add('cart-drawer__overlay--visible');
      document.body.style.overflow = 'hidden';
    }

    function close() {
      drawer.classList.remove('cart-drawer--open');
      overlay.classList.remove('cart-drawer__overlay--visible');
      document.body.style.overflow = '';
    }

    openTriggers.forEach((t) => t.addEventListener('click', open));
    closeBtn && closeBtn.addEventListener('click', close);
    overlay && overlay.addEventListener('click', close);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
  }

  /* --- ATC with drawer open --- */
  function initATC() {
    const forms = document.querySelectorAll('[data-atc-form]');

    forms.forEach((form) => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('[data-atc-btn]');
        if (!btn) return;

        btn.classList.add('product-atc__btn--loading');
        btn.textContent = 'Adding...';

        try {
          const formData = new FormData(form);
          const body = { items: [{ id: formData.get('id'), quantity: 1 }] };

          const res = await fetch('/cart/add.js', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });

          if (res.ok) {
            await refreshCartDrawer();
            const drawer = document.getElementById('cart-drawer');
            const overlay = document.getElementById('cart-overlay');
            if (drawer) {
              drawer.classList.add('cart-drawer--open');
              overlay && overlay.classList.add('cart-drawer__overlay--visible');
              document.body.style.overflow = 'hidden';
            }
            btn.textContent = 'Added';
            setTimeout(() => {
              btn.textContent = 'Add to Cart';
              btn.classList.remove('product-atc__btn--loading');
            }, 2000);
          }
        } catch {
          btn.textContent = 'Add to Cart';
          btn.classList.remove('product-atc__btn--loading');
        }
      });
    });
  }

  /* --- Refresh cart count badge --- */
  async function refreshCartDrawer() {
    try {
      const res = await fetch('/cart.js');
      const cart = await res.json();
      const countEl = document.querySelector('[data-cart-count]');
      if (countEl) countEl.textContent = cart.item_count;
    } catch {
      // silently fail
    }
  }

  /* --- Bundle checkbox total updater --- */
  function initBundleTotal() {
    const bundle = document.querySelector('[data-bundle]');
    if (!bundle) return;

    const checkboxes = bundle.querySelectorAll('[data-bundle-item]');
    const totalEl = bundle.querySelector('[data-bundle-total]');

    function updateTotal() {
      let total = 0;
      checkboxes.forEach((cb) => {
        if (cb.checked) {
          total += parseInt(cb.dataset.price || 0, 10);
        }
      });
      if (totalEl) {
        totalEl.textContent = (total / 100).toLocaleString('en-US', {
          style: 'currency',
          currency: 'USD',
        });
      }
    }

    checkboxes.forEach((cb) => cb.addEventListener('change', updateTotal));
    updateTotal();
  }

  /* --- Init --- */
  document.addEventListener('DOMContentLoaded', () => {
    initFadeIn();
    initProductTabs();
    initCartDrawer();
    initATC();
    initBundleTotal();
  });
})();
