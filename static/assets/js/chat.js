const chatForm       = document.getElementById('chat-form');
const userInput      = document.getElementById('user-input');
const chatBox        = document.getElementById('chat-box');
const sendBtn        = document.getElementById('send-btn');
const typingIndicator= document.getElementById('typing-indicator');
const scrollTopBtn   = document.getElementById('scroll-top');
const themeToggle    = document.getElementById('theme-toggle');

function addMessage(text, sender) {
  const msg = document.createElement('div');
  msg.className = `message ${sender}`;
  msg.innerHTML = `
    <p class="text">${text}</p>
    <span class="timestamp">${new Date().toLocaleTimeString('ar-EG')}</span>
  `;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping(show) {
  typingIndicator.classList.toggle('hidden', !show);
}

chatBox.addEventListener('scroll', () => {
  scrollTopBtn.classList.toggle('hidden', chatBox.scrollTop <= 200);
});
scrollTopBtn.addEventListener('click', () => (chatBox.scrollTop = 0));

themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark');
  const icon = document.body.classList.contains('dark') ? '☀️' : '🌙';
  themeToggle.textContent = icon;
  localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
});
document.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark');
    themeToggle.textContent = '☀️';
  }
});

chatForm.addEventListener('submit', async e => {
  e.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;
  addMessage(message, 'user');
  userInput.value = '';
  sendBtn.disabled = true;
  showTyping(true);
  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    showTyping(false);
    addMessage(data.response, 'bot');
  } catch {
    showTyping(false);
    addMessage('حدث خطأ، حاول لاحقًا...', 'bot');
  }
  sendBtn.disabled = false;
});