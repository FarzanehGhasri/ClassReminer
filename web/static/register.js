/*
 * Form behaviour: screen switching, the country picker, live hints, and the
 * POST to /api/register.
 *
 * The validation here is a convenience so a student sees a mistake before
 * submitting. It is NOT the guarantee: core/models/ re-validates every field
 * on the server, and the database domains reject anything that gets past both.
 * The rules come from /api/countries, so this file never hard-codes a country.
 */
(function () {
  "use strict";

  var COUNTRIES = JSON.parse(document.getElementById("countryData").textContent);
  var selected = COUNTRIES[0];

  var PERSIAN_NAME = /^[ء-غف-يپچژھکگی]+(?:[ ‌\-][ء-غف-يپچژھکگی]+)*$/;
  // Mirrors utils/validator.EMAIL_PATTERN and the email_address SQL domain.
  var EMAIL = /^[A-Za-z0-9!#$%&'*+\/=?^_`{|}~.-]+@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$/;
  var FA_DIGITS = /[۰-۹٠-٩]/g;

  function el(id) { return document.getElementById(id); }

  /* ---------- screens ---------- */
  function goTo(n) {
    [1, 2, 3].forEach(function (i) {
      el("screen" + i).classList.toggle("hidden", i !== n);
    });
    window.scrollTo(0, 0);
  }
  document.querySelectorAll("[data-goto]").forEach(function (btn) {
    btn.addEventListener("click", function () { goTo(Number(btn.dataset.goto)); });
  });

  /* ---------- digits ---------- */
  function toLatinDigits(s) {
    return s.replace(FA_DIGITS, function (d) {
      var i = "۰۱۲۳۴۵۶۷۸۹".indexOf(d);
      if (i < 0) i = "٠١٢٣٤٥٦٧٨٩".indexOf(d);
      return String(i);
    });
  }

  /* Mirrors _find_national_number in core/models/phone_number.py. */
  function nationalNumber(raw, country) {
    var text = toLatinDigits(String(raw || "").trim()).replace(/[\s\-().]/g, "");
    if (text.indexOf("00") === 0) text = "+" + text.slice(2);
    var explicit = text.charAt(0) === "+";
    var body = text.replace(/\D/g, "");
    if (!body) return null;

    var dial = country.dial_code.replace("+", "");
    var trunk = country.trunk_prefix;
    var rule = new RegExp("^(?:" + country.national_pattern + ")$");
    var candidates = [];

    if (explicit && body.indexOf(dial) !== 0) return null;

    if (body.indexOf(dial) === 0) candidates.push(body.slice(dial.length));
    if (!explicit) {
      candidates.push(body);
      if (trunk && body.indexOf(trunk) === 0) candidates.push(body.slice(trunk.length));
    } else {
      var trimmed = body.slice(dial.length);
      if (trunk && trimmed.indexOf(trunk) === 0) candidates.push(trimmed.slice(trunk.length));
    }

    for (var i = 0; i < candidates.length; i++) {
      if (rule.test(candidates[i])) return candidates[i];
    }
    return null;
  }

  /* ---------- country picker ---------- */
  function applyCountry(country) {
    selected = country;
    el("cFlag").textContent = country.flag;
    el("cDial").textContent = country.dial_code;
    el("phone").placeholder = country.example_local;
    el("phoneHint").innerHTML =
      "<b>مثال:</b> " + escapeHtml(country.example_local) + " — " + escapeHtml(country.hint_fa);
    el("countryBtn").setAttribute(
      "aria-label", "کشور: " + country.name_fa + " " + country.dial_code
    );
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderList(filter) {
    var list = el("countryList");
    var q = (filter || "").trim().toLowerCase();
    var matches = COUNTRIES.filter(function (c) {
      return !q || c.name_fa.indexOf(q) >= 0 ||
        c.dial_code.indexOf(q) >= 0 || c.iso.toLowerCase().indexOf(q) >= 0;
    });

    list.innerHTML = "";
    if (!matches.length) {
      var empty = document.createElement("li");
      empty.className = "sheet-empty";
      empty.textContent = "کشوری پیدا نشد.";
      list.appendChild(empty);
      return;
    }
    matches.forEach(function (c) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-selected", String(c.iso === selected.iso));
      btn.innerHTML =
        '<span class="s-flag">' + c.flag + '</span>' +
        '<span class="s-name">' + escapeHtml(c.name_fa) + '</span>' +
        '<span class="s-dial">' + escapeHtml(c.dial_code) + '</span>';
      btn.addEventListener("click", function () {
        applyCountry(c);
        closeSheet();
        clearError("phone");
        el("phone").focus();
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
  }

  function openSheet() {
    el("sheetBackdrop").classList.remove("hidden");
    el("countryBtn").setAttribute("aria-expanded", "true");
    el("countrySearch").value = "";
    renderList("");
    el("countrySearch").focus();
  }
  function closeSheet() {
    el("sheetBackdrop").classList.add("hidden");
    el("countryBtn").setAttribute("aria-expanded", "false");
    el("countryBtn").focus();
  }

  el("countryBtn").addEventListener("click", openSheet);
  el("sheetClose").addEventListener("click", closeSheet);
  el("sheetBackdrop").addEventListener("click", function (e) {
    if (e.target === el("sheetBackdrop")) closeSheet();
  });
  el("countrySearch").addEventListener("input", function (e) { renderList(e.target.value); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !el("sheetBackdrop").classList.contains("hidden")) closeSheet();
  });

  /* ---------- errors ---------- */
  function setError(field, message) {
    var box = el("err-" + field);
    var input = el(field);
    if (box) { box.textContent = message; box.classList.add("show"); }
    if (input) input.classList.add("invalid");
  }
  function clearError(field) {
    var box = el("err-" + field);
    var input = el(field);
    if (box) { box.textContent = ""; box.classList.remove("show"); }
    if (input) input.classList.remove("invalid");
  }
  function clearAll() {
    ["first_name", "last_name", "phone", "email", "country", "form"].forEach(clearError);
  }

  ["first_name", "last_name", "phone", "email"].forEach(function (id) {
    el(id).addEventListener("input", function () { clearError(id); });
  });

  /* ---------- submit ---------- */
  el("regForm").addEventListener("submit", function (e) {
    e.preventDefault();
    clearAll();

    var first = el("first_name").value.trim();
    var last = el("last_name").value.trim();
    var phoneRaw = el("phone").value.trim();
    var email = el("email").value.trim();
    var bad = false;

    if (!first) { setError("first_name", "نام را وارد کنید."); bad = true; }
    else if (!PERSIAN_NAME.test(first)) { setError("first_name", "نام باید فقط با حروف فارسی نوشته شود."); bad = true; }

    if (!last) { setError("last_name", "نام خانوادگی را وارد کنید."); bad = true; }
    else if (!PERSIAN_NAME.test(last)) { setError("last_name", "نام خانوادگی باید فقط با حروف فارسی نوشته شود."); bad = true; }

    if (!phoneRaw) { setError("phone", "شماره تماس را وارد کنید."); bad = true; }
    else if (!nationalNumber(phoneRaw, selected)) {
      setError("phone", "شماره برای " + selected.name_fa + " معتبر نیست — " + selected.hint_fa + ".");
      bad = true;
    }

    if (!email) { setError("email", "ایمیل را وارد کنید."); bad = true; }
    else if (!EMAIL.test(email) || email.indexOf("..") >= 0 || email.length > 254) {
      setError("email", "فرمت ایمیل صحیح نیست."); bad = true;
    }

    if (bad) return;

    var btn = el("submitBtn");
    btn.disabled = true;
    btn.textContent = "در حال ثبت…";

    fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: first, last_name: last,
        phone: phoneRaw, email: email, country: selected.iso
      })
    })
      .then(function (res) { return res.json().then(function (b) { return { status: res.status, body: b }; }); })
      .then(function (r) {
        if (r.status === 201 && r.body.ok) {
          el("successSub").textContent =
            (r.body.full_name ? r.body.full_name + " عزیز، " : "") +
            "اطلاعات شما ذخیره شد. کارشناسان آکادمی به‌زودی با شما تماس می‌گیرند.";
          el("regForm").reset();
          applyCountry(COUNTRIES[0]);
          goTo(3);
          return;
        }
        var errors = (r.body && r.body.errors) || { form: "ثبت انجام نشد. دوباره تلاش کنید." };
        Object.keys(errors).forEach(function (field) { setError(field, errors[field]); });
      })
      .catch(function () {
        setError("form", "ارتباط با سرور برقرار نشد. اتصال خود را بررسی کنید.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "ثبت اطلاعات";
      });
  });

  applyCountry(selected);
})();
