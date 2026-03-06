--[[
  Load_and_Render.lua
  Загружает шаблон Ozone_Master_Template.RPP, подставляет аудиофайл на первую дорожку,
  рендерит мастер в WAV без нормализации.
  Вызов: нужны пути к шаблону и к аудиофайлу (через reaper.GetUserInputs или переданные извне).
  Рендер: File -> Render, настройки без нормализации.
]]

local function get_paths()
  local template_path = reaper.GetExtState("OzoneMaster", "TemplatePath")
  local audio_path = reaper.GetExtState("OzoneMaster", "AudioPath")
  if template_path == "" or audio_path == "" then
    local ok, vals = reaper.GetUserInputs("Мастеринг", 2, "Путь к шаблону .RPP,Путь к аудиофайлу", template_path .. "," .. audio_path)
    if not ok then return nil, nil end
    template_path, audio_path = vals:match("([^,]+),([^,]+)")
    if template_path then reaper.SetExtState("OzoneMaster", "TemplatePath", template_path, true) end
    if audio_path then reaper.SetExtState("OzoneMaster", "AudioPath", audio_path, true) end
  end
  return template_path, audio_path
end

local template_path, audio_path = get_paths()
if not template_path or not audio_path or template_path == "" or audio_path == "" then
  reaper.ShowMessageBox("Укажите путь к шаблону и к аудиофайлу.", "Ошибка", 0)
  return
end

if not reaper.FileExists(template_path) then
  reaper.ShowMessageBox("Файл шаблона не найден:\n" .. template_path, "Ошибка", 0)
  return
end

if not reaper.FileExists(audio_path) then
  reaper.ShowMessageBox("Аудиофайл не найден:\n" .. audio_path, "Ошибка", 0)
  return
end

-- Открыть шаблон (Reaper 6+: Main_openProject(proj, path, forceAddToTab))
local ok = reaper.Main_openProject(0, template_path, false)
if not ok then
  reaper.ShowMessageBox("Не удалось открыть шаблон. Откройте " .. template_path .. " вручную и запустите скрипт снова.", "Ошибка", 0)
  return
end

local track = reaper.GetTrack(0, 0)
if not track then
  reaper.ShowMessageBox("В шаблоне нет первой дорожки.", "Ошибка", 0)
  return
end

reaper.SetOnlyTrackSelected(track)
reaper.SetEditCurPos(0, true, false)
-- Вставить медиа из файла (Reaper 6+)
reaper.InsertMedia(audio_path, 0)
reaper.UpdateArrange()

-- Рендер без нормализации: открыть диалог рендера
reaper.Main_OnCommand(41824, 0) -- File: Render project to file
reaper.ShowMessageBox("В диалоге рендера снимите 'Normalize'. Укажите путь и нажмите Render.", "Рендер", 0)
