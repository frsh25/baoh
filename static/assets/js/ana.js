document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("analyze-form");
  
    form.addEventListener("submit", function(e) {
      e.preventDefault();
  
      // عرض شكلي فقط (نتيجة عشوائية)
      const results = [
        { sentiment: "إيجابي", data: [20, 60, 20] },
        { sentiment: "سلبي", data: [10, 20, 70] },
        { sentiment: "محايد", data: [70, 10, 20] }
      ];
  
      const randomResult = results[Math.floor(Math.random() * results.length)];
  
      document.getElementById("result-box").style.display = "block";
      document.getElementById("sentiment-text").textContent = "الحالة العامة: " + randomResult.sentiment;
  
      const ctx = document.getElementById("sentiment-chart").getContext("2d");
  
      if (window.sentimentChart) {
        window.sentimentChart.destroy();
      }
  
      window.sentimentChart = new Chart(ctx, {
        type: "pie",
        data: {
          labels: ["محايد", "إيجابي", "سلبي"],
          datasets: [{
            data: randomResult.data,
            backgroundColor: ["#cccccc", "#4caf50", "#f44336"]
          }]
        },
        options: {
          responsive: true
        }
      });
    });
  });
  