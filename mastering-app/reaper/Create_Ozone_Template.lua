--[[
  Create_Ozone_Template.lua
  Создаёт проект-шаблон для мастеринга: одна дорожка + мастер.
  Пользователь вручную добавляет Ozone на мастер и выбирает пресет "House Master - Basic".
  Запуск: Reaper -> Extensions -> ReaScript -> Run.
  Сохраните проект как Ozone_Master_Template.RPP в папку Scripts или укажите путь в Load_and_Render.
]]

reaper.Main_OnCommand(40020, 0) -- File: New project

if reaper.CountTracks(0) == 0 then
  reaper.InsertTrackAtIndex(0, true)
end

local master_track = reaper.GetMasterTrack(0)
if master_track then
  reaper.TrackFX_AddByName(master_track, "VST3:iZotope Ozone 5", false, -1)
  reaper.TrackFX_AddByName(master_track, "VST3:Ozone 9", false, -1)
  reaper.TrackFX_AddByName(master_track, "VST:iZotope Ozone", false, -1)
end

reaper.ShowMessageBox(
  "1. Добавьте iZotope Ozone на мастер-шину (Master Track).\n" ..
  "2. Выберите пресет 'House Master - Basic' или 'House Basic'.\n" ..
  "3. Сохраните проект (File -> Save project as) как Ozone_Master_Template.RPP в удобную папку.",
  "Создание шаблона",
  0
)

reaper.Main_OnCommand(40022, 0) -- File: Save project as
