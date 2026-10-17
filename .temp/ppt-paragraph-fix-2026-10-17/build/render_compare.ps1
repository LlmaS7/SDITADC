$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class PptParagraphReview {
 [DllImport("oleaut32.dll", PreserveSig=false)] public static extern void GetActiveObject(ref Guid clsid, IntPtr reserved, [MarshalAs(UnmanagedType.IUnknown)] out object instance);
}
'@
$pptType=[type]::GetTypeFromProgID('PowerPoint.Application');$pptGuid=$pptType.GUID;$pptApp=$null
[PptParagraphReview]::GetActiveObject([ref]$pptGuid,[IntPtr]::Zero,[ref]$pptApp)
$source=$pptApp.Presentations | Where-Object {$_.FullName -eq 'E:\_PROJECTS\temp\global-governance\exports\奉行主权平等_课堂演讲_精排版.pptx'} | Select-Object -First 1
if (-not $source) {throw 'Original deck is no longer open'}
$candidatePath=Join-Path $root 'build\paragraph-candidate.pptx'
$fixed=$pptApp.Presentations.Open($candidatePath,-1,0,0)
try {
  $fixed.Export((Join-Path $root 'after'),'PNG',1280,720)
  $plan=Get-Content -LiteralPath (Join-Path $root 'build\merge-plan.json') -Raw | ConvertFrom-Json
  $measurements=@()
  foreach($group in $plan){
    $merged=$fixed.Slides.Item([int]$group.slide).Shapes.Item([string]$group.originals[0].name)
    $range=$merged.TextFrame2.TextRange
    $lines=@()
    for($i=0;$i -lt $group.originals.Count;$i++){
      $old=$source.Slides.Item([int]$group.slide).Shapes.Item([string]$group.originals[$i].name).TextFrame2.TextRange
      $new=$range.Lines(($i+1),1)
      $lines+=[pscustomobject]@{index=$i;beforeTop=[double]$old.BoundTop;afterTop=[double]$new.BoundTop;beforeLeft=[double]$old.BoundLeft;afterLeft=[double]$new.BoundLeft;beforeText=$old.Text;afterText=$new.Text}
    }
    $measurements+=[pscustomobject]@{slide=$group.slide;name=$group.originals[0].name;paragraphCount=$range.Paragraphs().Count;lineCount=$range.Lines().Count;expectedLines=$group.originals.Count;lines=$lines}
  }
  $measurements | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $root 'build\native-text-measurements.json') -Encoding utf8
  [pscustomobject]@{slides=$fixed.Slides.Count;paragraphs=$measurements.Count;allSingleParagraph=(@($measurements | Where-Object {$_.paragraphCount -ne 1}).Count -eq 0);allExpectedLineCounts=(@($measurements | Where-Object {$_.lineCount -ne $_.expectedLines}).Count -eq 0);originalSavedStatus=[int]$source.Saved} | ConvertTo-Json
} finally {$fixed.Close()}
