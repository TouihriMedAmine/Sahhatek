document.addEventListener('DOMContentLoaded', () => {
  // --- Elements ---
  const authModal = document.getElementById('authModal');
  const loginBtn = document.getElementById('loginBtn');
  const signupBtn = document.getElementById('signupBtn');
  const closeModal = document.getElementById('closeModal');

  const loginFormWrapper = document.getElementById('loginForm');
  const signupFormWrapper = document.getElementById('signupForm');
  const switchToSignup = document.getElementById('switchToSignup');
  const switchToLogin = document.getElementById('switchToLogin');

  const loginForm = document.getElementById('loginFormElement');
  const signupStep1 = document.getElementById('signupFormStep1');
  const signupStep2 = document.getElementById('signupFormStep2');

  const sendCodeBtn = document.getElementById('sendSignupCode');
  const verifyCodeBtn = document.getElementById('verifySignupCode');
  const resendCodeBtn = document.getElementById('resendCode');

  // --- CSRF ---
  function getCSRFToken() {
    const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  }
  const csrftoken = getCSRFToken();

   // --- MODAL CONTROL ---
  function openModal(form) {
    authModal.classList.remove('hidden');

    if (form === 'login') {
      loginFormWrapper.classList.remove('hidden');
      signupFormWrapper.classList.add('hidden');
      signupStep1.classList.remove('hidden');
      signupStep2.classList.add('hidden');
    } else {
      signupFormWrapper.classList.remove('hidden');
      loginFormWrapper.classList.add('hidden');
      signupStep1.classList.remove('hidden');
      signupStep2.classList.add('hidden');
    }
  }
  
  function closeAuthModal() {
    authModal.classList.add('hidden');
  }

  if (loginBtn) loginBtn.addEventListener('click', () => openModal('login'));
  if (signupBtn) signupBtn.addEventListener('click', () => openModal('signup'));
  closeModal.addEventListener('click', closeAuthModal);

  // --- SWITCH FORMS ---
  switchToSignup.addEventListener('click', () => openModal('signup'));
  switchToLogin.addEventListener('click', () => openModal('login'));

  // --- LOGIN SUBMIT ---
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = loginForm.username.value.trim();
    const password = loginForm.password.value.trim();

    try {
      const res = await fetch("/auth/login/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      alert(data.message);
      if (data.success) window.location.href = "/chat/";
    } catch (err) {
      alert("Login failed.");
    }
  });

  // --- SIGNUP STEP 1 ---
  sendCodeBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const payload = {
      username: signupStep1.username.value.trim(),
      email: signupStep1.email.value.trim(),
      phone: signupStep1.phone.value.trim(),
      password1: signupStep1.password1.value.trim(),
      password2: signupStep1.password2.value.trim()
    };

    try {
      const res = await fetch("/auth/signup/", {   // Matches urls.py
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      alert(data.message);
      if (data.success) {
        signupStep1.classList.add('hidden');
        signupStep2.classList.remove('hidden');
        signupStep2.dataset.username = payload.username;
      }
    } catch (err) {
      alert("Signup failed.");
    }
  });

  // --- SIGNUP STEP 2 (VERIFY CODE) ---
  verifyCodeBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const code = signupStep2.querySelector('#verificationCode').value.trim();
    const username = signupStep2.dataset.username;

    try {
      const res = await fetch("/auth/verify/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify({ username, code })
      });
      const data = await res.json();
      alert(data.message);
      if (data.success) window.location.href = "/chat/";
    } catch (err) {
      alert("Verification error.");
    }
  });

  // --- RESEND CODE ---
  resendCodeBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const username = signupStep2.dataset.username;

    try {
      const res = await fetch("/auth/resend-code/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify({ username })
      });
      const data = await res.json();
      alert(data.message);
    } catch (err) {
      alert("Could not resend code.");
    }
  });
});
