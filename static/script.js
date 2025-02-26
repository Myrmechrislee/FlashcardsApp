let flipped = false;
function flipCard() {
    const card = document.getElementById('flashcard');
    const survey = document.getElementById('survey');
    if (!flipped) {
        card.style.transform = 'rotateY(180deg)';
        survey.style.display = 'block';
    } else {
        card.style.transform = 'rotateY(0deg)';
        survey.style.display = 'none';
    }
    flipped = !flipped;
}

function submitResponse(response) {
    fetch('/submitconfidence', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({tid: window.tid, qid: window.qid, confidence: response })
      })
      .then(res => {
        if (res.ok) {
          window.location.reload()
        } else {
          return res.json();
        }
      })
      .then(data => console.log(data))
      .catch(err => console.error(err));
}