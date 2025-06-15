// روابط التنزيل بعد حفظ التقرير
let downloadLinks = {
  pdf: null

  
};

document.addEventListener('DOMContentLoaded', () => {
  const config = window.barChartConfig;
  const meta = window.reportMeta;
  const csvId = window.csvId;
  if (!config || !meta || !csvId) return;

  // === إضافة ألوان مختلفة لكل عمود ===
  config.data.datasets[0].backgroundColor = [
    '#4CAF50', // أخضر للإيجابي
    '#F44336', // أحمر للسلبي
    '#FFC107'  // أصفر للمحايد
  ];
  config.data.datasets[0].borderColor = [
    '#388E3C', // حدود داكنة للأخضر
    '#D32F2F', // حدود داكنة للأحمر
    '#FFA000'  // حدود داكنة للأصفر
  ];
  config.data.datasets[0].borderWidth = 1;

  // === رسم المخطط ===
  const ctx = document.getElementById('barChart').getContext('2d');
  const chart = new Chart(ctx, config);

  chart.options.animation = {
    onComplete: () => saveReport()
  };

  // === دالة حفظ التقرير ===
  async function saveReport() {
    const dataUrl = document.getElementById('barChart').toDataURL('image/png');
    const payload = {
      csv_id: csvId,
      num_rows: meta.numRows,
      num_columns: meta.numColumns,
      total: meta.total,
      average: meta.average,
      labels: config.data.labels,
      counts: config.data.datasets[0].data,
      chart_image: dataUrl
    };

    try {
      const res = await fetch('/save_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      if (res.ok && result.status === 'success') {
        showNotification('✅ تم حفظ التقرير بنجاح.');
        downloadLinks.pdf = result.pdf_url;
        downloadLinks.csv = result.csv_url;
        downloadLinks.png = result.png_url;
      } else {
        showNotification(`❌ خطأ في الحفظ: ${result.error}`);
      }
    } catch (err) {
      console.error(err);
      showNotification('❌ حدث خطأ أثناء حفظ التقرير.');
    }
  }

  // === دالة لعرض الإشعارات ===
  function showNotification(msg) {
    const box = document.createElement('div');
    box.className = 'alert alert-info';
    box.style = 'position:fixed; top:20px; right:20px; z-index:9999;';
    box.textContent = msg;
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 4000);
  }

  // === تفعيل الأسئلة الشائعة FAQ ===
  const questions = document.querySelectorAll('.faq-question');
  questions.forEach(question => {
    question.addEventListener('click', () => {
      const answer = question.nextElementSibling;
      answer.style.display = answer.style.display === 'block' ? 'none' : 'block';
    });
  });
});

// === إظهار قائمة خيارات التحميل ===
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('download-report').addEventListener('click', () => {
    const downloadOptions = document.getElementById('download-options');
    downloadOptions.style.display = downloadOptions.style.display === 'none' ? 'block' : 'none';
  });

  // تحميل PDF
  document.getElementById('download-pdf').addEventListener('click', () => {
    if (downloadLinks.pdf) {
      window.location.href = downloadLinks.pdf;
    } else {
      alert('❌ التقرير غير جاهز بعد.');
    }
  });

  // تحميل PNG
  document.getElementById('download-png').addEventListener('click', () => {
    if (downloadLinks.png) {
      window.location.href = downloadLinks.png;
    } else {
      alert('❌ الصورة غير جاهزة بعد.');
    }
  });

  // تحميل CSV
  document.getElementById('download-csv').addEventListener('click', () => {
    if (downloadLinks.csv) {
      window.location.href = downloadLinks.csv;
    } else {
      alert('❌ ملف CSV غير جاهز بعد.');
    }
  });
});
