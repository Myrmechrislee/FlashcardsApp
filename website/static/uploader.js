document.addEventListener("DOMContentLoaded", function() {
  const fileInput = document.getElementById("csv-file");
  const fileUploadContainer = document.querySelector(".file-upload-container");
  const fileUploadLabel = document.querySelector(".file-upload");
  const deleteBtn = document.getElementById("delete-upload");
  
  fileInput.addEventListener("change", function() {
    if (fileInput.files.length > 0) {
      fileUploadLabel.classList.add("uploaded");
      fileUploadLabel.getElementsByTagName("span")[0].textContent = fileInput.files[0].name;
      deleteBtn.style.display = "inline-block";
    } else {
      fileUploadLabel.classList.remove("uploaded");
      fileUploadLabel.getElementsByTagName("span")[0].textContent = "Click or drag a file to upload";
      deleteBtn.style.display = "none";
    }
  });
  
  deleteBtn.addEventListener("click", function() {
    fileInput.value = "";
    fileUploadLabel.classList.remove("uploaded");
    fileUploadLabel.getElementsByTagName("span")[0].textContent = "Click or drag a file to upload";
    deleteBtn.style.display = "none";
  });
  
  fileUploadContainer.addEventListener("dragover", function(event) {
    event.preventDefault();
    fileUploadContainer.classList.add("dragover");
  });
  
  fileUploadContainer.addEventListener("dragleave", function() {
    fileUploadContainer.classList.remove("dragover");
  });
  
  fileUploadContainer.addEventListener("drop", function(event) {
    event.preventDefault();
    fileUploadContainer.classList.remove("dragover");
    
    const files = event.dataTransfer.files;
    if (files.length > 0) {
      if (files[0].type !== "text/csv") {
        alert("Only CSV files are allowed!");
        return;
      }
      fileInput.files = files;
      fileUploadLabel.classList.add("uploaded");
      fileUploadLabel.getElementsByTagName("span")[0].textContent = files[0].name;
      deleteBtn.style.display = "inline-block";
    }
  });
});