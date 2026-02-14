const cards = document.querySelectorAll(".service-card");
const totalValue = document.getElementById("totalValue");
const totalInput = document.getElementById("totalInput");
const menuToggle = document.getElementById("menu-toggle");
const navMenu = document.getElementById("nav-menu");
const menuOverlay = document.getElementById("menu-overlay");

// MENU (proteção contra null)
if (menuToggle && navMenu && menuOverlay) {

  menuToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      navMenu.classList.toggle("active");
      menuOverlay.classList.toggle("active");
  });

  menuOverlay.addEventListener("click", () => {
      navMenu.classList.remove("active");
      menuOverlay.classList.remove("active");
  });

}


cards.forEach(card => {
  const checkbox = card.querySelector("input");

  checkbox.addEventListener("change", function () {

    card.classList.toggle("active", this.checked);

    let total = 0;

    cards.forEach(c => {
      if (c.querySelector("input").checked) {
        total += Number(c.dataset.price);
      }
    });

    totalValue.textContent = total.toFixed(2);
    totalInput.value = total.toFixed(2);
  });
});



// DATA E HORÁRIOS
const dataInput = document.getElementById("data");
const msgData = document.getElementById("msgData");
const horariosContainer = document.getElementById("horarios");


dataInput.addEventListener("change", async () => {

  const dataSelecionada = dataInput.value;

  horariosContainer.innerHTML = "";
  msgData.textContent = "";

  const dataObj = new Date(dataSelecionada);
  const diaSemana = dataObj.getDay();

  if (diaSemana === 6 || diaSemana === 0) {
    msgData.textContent = "Trabalhamos apenas de terça a sábado.";
    return;
  }

  // 🔥 busca horários atualizados no servidor
  const response = await fetch(`/api/horarios/${dataSelecionada}`);
  const horariosOcupados = await response.json();

  const horarios = [
    "07:10","14:50","08:10","15:40","09:00","16:30",
    "09:50","17:20","10:40","18:10","11:30","19:00",
    "14:00","19:50",
  ];

  horarios.forEach(h => {

    const btn = document.createElement("div");
    btn.classList.add("horario-btn");
    btn.textContent = h;

    const ocupado = horariosOcupados.some(hOcupado => hOcupado.slice(0,5) === h);

    if (ocupado) {
        btn.classList.add("ocupado");
        btn.style.backgroundColor = "grey";
        btn.style.cursor = "not-allowed";
    } else {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".horario-btn")
              .forEach(b => b.classList.remove("active"));

            btn.classList.add("active");
            document.getElementById("horarioSelecionado").value = h;
        });
    }

    horariosContainer.appendChild(btn);
  });

});


const form = document.querySelector("form");

form.addEventListener("submit", function(e) {

  const servicosSelecionados = document.querySelectorAll(
    ".service-card input:checked"
  );

  const data = document.getElementById("data").value;
  const horario = document.getElementById("horarioSelecionado").value;
  const total = document.getElementById("totalInput").value;

  if (
    servicosSelecionados.length === 0 ||
    !data ||
    !horario ||
    total == 0
  ) {
    e.preventDefault();
    alert("Preencha todos os campos antes de confirmar.");
  }

});

const telefoneInput = document.getElementById("telefone");

telefoneInput.addEventListener("input", function (e) {
  let value = e.target.value.replace(/\D/g, ""); // remove tudo que não for número

  if (value.length > 11) {
    value = value.slice(0, 11);
  }

  if (value.length > 0) {
    value = "(" + value;
  }

  if (value.length > 2) {
    value = value.slice(0, 3) + ") " + value.slice(3);
  }

  if (value.length > 10) {
    value = value.slice(0, 10) + "-" + value.slice(10);
  }

  e.target.value = value;
});





